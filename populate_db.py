"""
populate_db.py  —  Manually build the people-search DB from an Excel file.

Usage (run from inside the brd_studio/ folder):

    # Auto-mode: reads every .xlsx / .xls file already in name_list/
    python populate_db.py

    # Pass a specific Excel file (copies it into name_list/ first):
    python populate_db.py "C:/Users/didar/Downloads/employees.xlsx"

Expected Excel columns (case-insensitive, order doesn't matter):
    EmployeeName  (or: Employee Name, Name, Full Name, EmpName, FullName)
    EmailId       (or: Email Id, Email, EmailAddress, E-Mail, Mail)

The script prints a summary and saves:
    brd_studio/data/users.db
"""

import sys
import sqlite3
import unicodedata
from pathlib import Path

# ── locate folders (same logic as app.py) ──────────────────────────────────
BASE_DIR      = Path(__file__).parent
NAME_LIST_DIR = BASE_DIR / "name_list"
DB_PATH       = BASE_DIR / "data" / "users.db"

NAME_LIST_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── column aliases ──────────────────────────────────────────────────────────
_NAME_ALIASES  = {"employeename", "employee name", "employee_name", "empname",
                   "name", "full name", "fullname", "full_name"}
_EMAIL_ALIASES = {"emailid", "email id", "email_id", "emailaddress",
                  "email", "e-mail", "mail", "email address"}


def _norm(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def _find_cols(header_row):
    name_col = email_col = None
    for ci, cell in enumerate(header_row):
        if cell is None:
            continue
        h = str(cell).strip().lower()
        h2 = h.replace(" ", "").replace("_", "")
        if h in _NAME_ALIASES or h2 in _NAME_ALIASES:
            name_col = ci
        elif h in _EMAIL_ALIASES or h2 in _EMAIL_ALIASES:
            email_col = ci
    return name_col, email_col


def parse_excel(path):
    """Return list of {name, email} dicts from one Excel file."""
    rows_out = []
    path = Path(path)
    print(f"  Parsing: {path.name}")
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        header = None
        name_col = email_col = None
        for row in ws.iter_rows(values_only=True):
            if header is None:
                header = row
                name_col, email_col = _find_cols(header)
                if name_col is None:
                    print(f"    WARNING: No name column found. Checked: {list(header)}")
                    print(f"    Expected one of: {sorted(_NAME_ALIASES)}")
                    break
                print(f"    Name column  → '{header[name_col]}'  (col {name_col})")
                if email_col is not None:
                    print(f"    Email column → '{header[email_col]}'  (col {email_col})")
                else:
                    print(f"    Email column → not found (emails will be blank)")
                continue
            name  = str(row[name_col]).strip()  if row[name_col]  is not None else ""
            email = str(row[email_col]).strip() if (email_col is not None and row[email_col] is not None) else ""
            if name and name.lower() not in ("none", "nan", ""):
                rows_out.append({"name": name, "email": email})
        wb.close()
    except ImportError:
        print("  ERROR: openpyxl not installed. Run: pip install openpyxl")
        sys.exit(1)
    except Exception as e:
        print(f"  ERROR reading {path.name}: {e}")
    return rows_out


def build_db(all_rows):
    """Write rows into users.db, replacing any previous data."""
    conn = sqlite3.connect(str(DB_PATH))
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
    conn.execute("DELETE FROM users")
    conn.executemany(
        "INSERT INTO users (name, email, designation, department, name_norm, email_norm) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (r["name"], r["email"], "", "",
             _norm(r["name"]), _norm(r["email"]))
            for r in all_rows
        ],
    )
    conn.commit()
    conn.close()


def main():
    # ── If a file path was passed as argument, copy it to name_list/ ─────────
    if len(sys.argv) > 1:
        src = Path(sys.argv[1])
        if not src.exists():
            print(f"ERROR: File not found: {src}")
            sys.exit(1)
        if not src.suffix.lower() in (".xlsx", ".xls"):
            print(f"ERROR: Only .xlsx and .xls files are supported.")
            sys.exit(1)
        dest = NAME_LIST_DIR / src.name
        import shutil
        shutil.copy2(src, dest)
        print(f"Copied {src.name} → name_list/")

    # ── Discover all Excel files in name_list/ ────────────────────────────────
    excel_files = sorted(NAME_LIST_DIR.glob("*.xls*"))
    if not excel_files:
        print()
        print("No Excel files found in name_list/")
        print(f"  Folder: {NAME_LIST_DIR.resolve()}")
        print()
        print("Either:")
        print("  1. Copy your Excel file into that folder, then re-run: python populate_db.py")
        print("  2. Pass the file path directly:  python populate_db.py employees.xlsx")
        sys.exit(1)

    # ── Parse each file, merge, deduplicate ──────────────────────────────────
    print(f"\nFound {len(excel_files)} file(s) in name_list/:")
    all_rows, seen = [], set()
    for f in excel_files:
        for row in parse_excel(f):
            key = row["email"].lower() if row["email"] else row["name"].lower()
            if key and key not in seen:
                seen.add(key)
                all_rows.append(row)

    if not all_rows:
        print("\nERROR: No records parsed. Check column names in your Excel file.")
        print(f"  Expected name column like: EmployeeName / Name / Full Name")
        print(f"  Expected email column like: EmailId / Email / E-Mail")
        sys.exit(1)

    # ── Write to DB ───────────────────────────────────────────────────────────
    build_db(all_rows)

    print(f"\n✓ Done!  {len(all_rows)} records written to:")
    print(f"  {DB_PATH.resolve()}")
    print()
    print("Now (re)start the Flask server — the search will use this DB automatically.")


if __name__ == "__main__":
    main()
