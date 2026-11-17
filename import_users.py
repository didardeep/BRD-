"""
import_users.py — Import a users spreadsheet into SQLite for the people-lookup feature.

Usage:
    python import_users.py path/to/users.xlsx
    python import_users.py path/to/users.xlsx --db path/to/users.db

Column auto-detection (case-insensitive):
    name        ← "name", "full name", "employee name", "display name"
    first_name  ← "first name", "first", "given name"
    last_name   ← "last name", "last", "surname", "family name"
    email       ← "email", "e-mail", "mail id", "email address"
    designation ← "designation", "title", "role", "job title"
    department  ← "department", "dept", "function", "team", "division"

If separate first/last name columns are found they are combined into name.
Blank rows and rows with no name are skipped.
Rows are de-duplicated by email (then by name).
The entire users table is replaced in one transaction.
"""

import sys
import os
from pathlib import Path


# ---------------------------------------------------------------------------
# Column header aliases
# ---------------------------------------------------------------------------

_ALIASES = {
    "name":        {"name", "full name", "employee name", "display name", "full_name"},
    "first_name":  {"first name", "first", "given name", "first_name", "firstname"},
    "last_name":   {"last name", "last", "surname", "family name", "last_name", "lastname"},
    "email":       {"email", "e-mail", "mail id", "email address", "email id"},
    "designation": {"designation", "title", "role", "job title", "position"},
    "department":  {"department", "dept", "function", "team", "division", "cost centre"},
}


def _match_col(header):
    """Return a canonical key for a spreadsheet column header, or None."""
    h = header.strip().lower()
    for key, aliases in _ALIASES.items():
        if h in aliases:
            return key
    return None


# ---------------------------------------------------------------------------
# Import logic
# ---------------------------------------------------------------------------

def import_users(xlsx_path, db_path=None):
    try:
        import openpyxl
    except ImportError:
        print("ERROR: openpyxl is required.  Run:  pip install openpyxl")
        sys.exit(1)

    from brd_agent.users_db import replace_all

    xlsx_path = Path(xlsx_path)
    if db_path is None:
        db_path = xlsx_path.parent / "users.db"
    db_path = Path(db_path)

    if not xlsx_path.exists():
        print(f"ERROR: File not found: {xlsx_path}")
        sys.exit(1)

    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active

    # --- Detect header row (first row with at least 2 recognised columns) ---
    header_row_idx = None
    col_map = {}  # canonical_key → 0-based column index

    for ri, row in enumerate(ws.iter_rows(values_only=True)):
        if row is None:
            continue
        candidate = {}
        for ci, cell in enumerate(row):
            if cell is None:
                continue
            key = _match_col(str(cell))
            if key:
                candidate[key] = ci
        if len(candidate) >= 2:
            header_row_idx = ri
            col_map = candidate
            break

    if header_row_idx is None:
        print("ERROR: Could not detect a valid header row.  "
              "Expected columns like 'Name', 'Email', 'Designation', 'Department'.")
        sys.exit(1)

    detected = ", ".join(f"{k}→col{v+1}" for k, v in col_map.items())
    print(f"Detected columns: {detected}")

    # --- Extract rows ---
    rows_out = []
    seen_email = set()
    seen_name  = set()
    skipped    = 0
    imported   = 0

    for ri, row in enumerate(ws.iter_rows(values_only=True)):
        if ri <= header_row_idx:
            continue
        if not row or all(c is None for c in row):
            continue

        def cell(key):
            idx = col_map.get(key)
            if idx is None or idx >= len(row):
                return ""
            return str(row[idx]).strip() if row[idx] is not None else ""

        # Build name
        name = cell("name")
        if not name:
            first = cell("first_name")
            last  = cell("last_name")
            if first or last:
                name = (first + " " + last).strip()
        if not name:
            skipped += 1
            continue

        email       = cell("email").lower()
        designation = cell("designation")
        department  = cell("department")

        # De-duplicate
        if email and email in seen_email:
            skipped += 1
            continue
        name_key = name.lower()
        if not email and name_key in seen_name:
            skipped += 1
            continue

        if email:
            seen_email.add(email)
        seen_name.add(name_key)

        rows_out.append({
            "name":        name,
            "email":       email,
            "designation": designation,
            "department":  department,
        })
        imported += 1

    wb.close()

    if not rows_out:
        print("WARNING: No valid rows found.  No data was imported.")
        return

    replace_all(str(db_path), rows_out)
    print(f"Imported {imported} users, skipped {skipped}.  Database: {db_path}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Import users from an Excel file into users.db")
    parser.add_argument("xlsx", help="Path to the Excel file (.xlsx)")
    parser.add_argument("--db", default=None,
                        help="Path to the SQLite database (default: same dir as xlsx, named users.db)")
    args = parser.parse_args()

    # Ensure brd_agent is importable when run from the brd_studio root
    script_dir = Path(__file__).parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))

    import_users(args.xlsx, args.db)
