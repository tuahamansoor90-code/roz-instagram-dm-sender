"""
importer.py - CSV / Excel contact importer for Instagram DM Sender
"""

import os
import pandas as pd
import database as db


def import_contacts(filepath: str) -> tuple[int, int, list[str]]:
    """
    Import contacts from a CSV or Excel file.

    Expected columns (case-insensitive):
        - username  (required)
        - name      (optional)

    Returns:
        (imported_count, skipped_count, error_messages)
    """
    if not os.path.exists(filepath):
        return 0, 0, [f"File not found: {filepath}"]

    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".csv":
            df = pd.read_csv(filepath, dtype=str)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(filepath, dtype=str)
        elif ext == ".txt":
            return _import_txt(filepath)
        else:
            return 0, 0, [f"Unsupported file type: {ext}. Use .csv, .xlsx or .txt"]
    except Exception as e:
        return 0, 0, [f"Failed to read file: {e}"]

    # Normalize column names
    df.columns = [c.strip().lower() for c in df.columns]

    if "username" not in df.columns:
        return 0, 0, [
            "No 'username' column found. "
            f"Columns in file: {', '.join(df.columns)}"
        ]

    imported = 0
    skipped  = 0
    errors: list[str] = []

    for idx, row in df.iterrows():
        raw_username = str(row.get("username", "")).strip()
        if not raw_username or raw_username.lower() == "nan":
            skipped += 1
            continue

        # Strip @ prefix if present
        username = raw_username.lstrip("@")
        name = ""
        if "name" in df.columns:
            raw_name = str(row.get("name", "")).strip()
            name = "" if raw_name.lower() == "nan" else raw_name

        try:
            added = db.add_contact(username, name)
            if added:
                imported += 1
            else:
                skipped += 1   # duplicate
        except Exception as e:
            errors.append(f"Row {idx + 2}: {e}")
            skipped += 1

    return imported, skipped, errors


def _import_txt(filepath: str) -> tuple[int, int, list[str]]:
    """
    Import usernames from a plain .txt file.
    Format — one username per line:
        @john_doe
        jane123
        # this is a comment (ignored)
        another_user
    """
    imported = 0
    skipped  = 0
    errors: list[str] = []

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        return 0, 0, [f"Failed to read file: {e}"]

    for i, line in enumerate(lines, start=1):
        raw = line.strip()

        # Skip blank lines and comment lines
        if not raw or raw.startswith("#"):
            continue

        # Strip @ prefix and any trailing whitespace
        username = raw.lstrip("@").strip()

        if not username:
            skipped += 1
            continue

        # Basic sanity check — Instagram usernames: letters, numbers, dots, underscores
        if " " in username:
            errors.append(f"Line {i}: '{raw}' looks invalid (contains space) — skipped")
            skipped += 1
            continue

        try:
            added = db.add_contact(username, "")
            if added:
                imported += 1
            else:
                skipped += 1   # duplicate
        except Exception as e:
            errors.append(f"Line {i}: {e}")
            skipped += 1

    return imported, skipped, errors
