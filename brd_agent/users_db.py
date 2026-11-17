"""
users_db.py — SQLite-backed user directory for name auto-complete.

Schema:
    users(id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          email TEXT,
          designation TEXT,
          department TEXT,
          name_norm TEXT,   -- lower-cased, accent-stripped for search
          email_norm TEXT)  -- lower-cased

Populate with import_users.py (or place data/users.xlsx to trigger auto-import).
"""

import sqlite3
import unicodedata
import difflib

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _norm(s):
    """Lowercase, strip accents, collapse whitespace."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def create_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            email       TEXT,
            designation TEXT,
            department  TEXT,
            name_norm   TEXT,
            email_norm  TEXT
        )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_name_norm  ON users(name_norm)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_email_norm ON users(email_norm)")
    conn.commit()


# ---------------------------------------------------------------------------
# bulk import (called from import_users.py)
# ---------------------------------------------------------------------------

def replace_all(db_path, rows):
    """Replace the entire users table in one transaction.

    rows: list of dicts with keys: name, email, designation, department
    """
    import os
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    create_schema(conn)
    conn.execute("DELETE FROM users")
    conn.executemany(
        "INSERT INTO users (name, email, designation, department, name_norm, email_norm) "
        "VALUES (:name, :email, :designation, :department, :name_norm, :email_norm)",
        [
            {
                "name":        r.get("name", ""),
                "email":       r.get("email", ""),
                "designation": r.get("designation", ""),
                "department":  r.get("department", ""),
                "name_norm":   _norm(r.get("name", "")),
                "email_norm":  _norm(r.get("email", "")),
            }
            for r in rows
        ],
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# search  (called from app.py  /api/users/search)
# ---------------------------------------------------------------------------

def search_users(db_path, q, limit=8):
    """Ranked user search.

    Ranking (lower = better):
      0 – exact name match
      1 – name starts with q
      2 – any word in name starts with q
      3 – name contains q
      4 – exact email match  (when q contains @)
      4 – email local-part starts with q  (when q has no @)
      5 – fuzzy difflib ratio >= 0.6
    """
    if not q or len(q) < 2:
        return []

    qn = _norm(q)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    has_at = "@" in qn

    if has_at:
        # Exact + prefix email match
        candidate_rows = conn.execute(
            "SELECT name, email, designation, department, name_norm, email_norm "
            "FROM users WHERE email_norm = ? OR email_norm LIKE ? LIMIT ?",
            (qn, qn + "%", limit * 4),
        ).fetchall()
    else:
        # Broad LIKE on name and email local part; also fetch all for fuzzy
        candidate_rows = conn.execute(
            "SELECT name, email, designation, department, name_norm, email_norm "
            "FROM users WHERE name_norm LIKE ? OR email_norm LIKE ? LIMIT ?",
            ("%" + qn + "%", "%" + qn + "%", limit * 5),
        ).fetchall()

        # If not enough hits, add fuzzy candidates from the full table (max 200)
        if len(candidate_rows) < limit:
            all_rows = conn.execute(
                "SELECT name, email, designation, department, name_norm, email_norm "
                "FROM users LIMIT 200"
            ).fetchall()
            seen = {r["email_norm"] or r["name_norm"] for r in candidate_rows}
            for r in all_rows:
                key = r["email_norm"] or r["name_norm"]
                if key not in seen:
                    ratio = difflib.SequenceMatcher(None, qn, r["name_norm"]).ratio()
                    if ratio >= 0.6:
                        candidate_rows = list(candidate_rows) + [r]
                        seen.add(key)

    conn.close()

    def _rank(row):
        nn    = row["name_norm"]
        en    = row["email_norm"] or ""
        local = en.split("@")[0] if "@" in en else en
        if has_at:
            if en == qn:
                return 0
            if en.startswith(qn):
                return 1
            ratio = difflib.SequenceMatcher(None, qn, en).ratio()
            return 2 + (1 - ratio) if ratio >= 0.5 else 99
        # non-email query
        if nn == qn:
            return 0
        if nn.startswith(qn):
            return 1
        if any(w.startswith(qn) for w in nn.split()):
            return 2
        if qn in nn:
            return 3
        if local.startswith(qn):
            return 4
        ratio = difflib.SequenceMatcher(None, qn, nn).ratio()
        if ratio >= 0.6:
            return 5 + (1 - ratio)
        return 99

    ranked = sorted(candidate_rows, key=_rank)
    ranked = [r for r in ranked if _rank(r) < 99][:limit]

    return [
        {
            "name":        r["name"],
            "email":       r["email"] or "",
            "designation": r["designation"] or "",
            "department":  r["department"] or "",
        }
        for r in ranked
    ]
