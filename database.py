"""
database.py - SQLite Database Handler for Instagram DM Sender
"""

import sqlite3
import os
from datetime import datetime


import sys

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "instagram_dm.db")


def get_connection():
    """Get a database connection with row_factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db():
    """Create all required tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # Contacts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT NOT NULL UNIQUE,
            name        TEXT,
            status      TEXT DEFAULT 'Pending',
            error_msg   TEXT,
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            sent_at     TEXT
        )
    """)

    # Settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            username  TEXT,
            name      TEXT,
            status    TEXT,
            error_msg TEXT,
            timestamp TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # Insert default settings if not present
    defaults = {
        "min_delay":        "60",
        "max_delay":        "180",
        "daily_limit":      "30",
        "batch_size":       "10",
        "batch_break_min":  "20",
        "batch_break_max":  "30",
        "browser_path":     "",
        "message_template": "Hi {{name}}, I wanted to reach out to you!",
        "session_active":   "0",
        "logged_in_user":   "",
    }
    for key, value in defaults.items():
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )

    conn.commit()
    conn.close()


# ──────────────────────────────────────────────────────────────
#  CONTACTS
# ──────────────────────────────────────────────────────────────

def add_contact(username: str, name: str = "") -> bool:
    """Insert a new contact. Returns True if inserted, False if already exists."""
    try:
        conn = get_connection()
        conn.execute(
            "INSERT OR IGNORE INTO contacts (username, name) VALUES (?, ?)",
            (username.strip(), name.strip()),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def get_all_contacts() -> list:
    """Return all contacts as a list of dicts."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, username, name, status, error_msg, created_at, sent_at "
        "FROM contacts ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_pending_contacts() -> list:
    """Return only contacts with status = 'Pending'."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, username, name FROM contacts WHERE status = 'Pending' ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_contact_status(username: str, status: str, error_msg: str = "") -> None:
    """Update the status (Sent / Failed) and optional error message for a contact."""
    sent_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == "Sent" else None
    conn = get_connection()
    conn.execute(
        "UPDATE contacts SET status = ?, error_msg = ?, sent_at = ? WHERE username = ?",
        (status, error_msg, sent_at, username),
    )
    conn.commit()
    conn.close()


def reset_contact_statuses() -> None:
    """Reset all Sent/Failed contacts back to Pending (useful for re-runs)."""
    conn = get_connection()
    conn.execute("UPDATE contacts SET status = 'Pending', error_msg = NULL, sent_at = NULL")
    conn.commit()
    conn.close()


def clear_contacts() -> None:
    """Delete all contacts from the table."""
    conn = get_connection()
    conn.execute("DELETE FROM contacts")
    conn.commit()
    conn.close()


def get_sent_count_today() -> int:
    """Count how many messages were sent today (for daily limit enforcement)."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM contacts WHERE status = 'Sent' AND sent_at LIKE ?",
        (f"{today}%",),
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


# ──────────────────────────────────────────────────────────────
#  SETTINGS
# ──────────────────────────────────────────────────────────────

def get_all_settings() -> dict:
    """Return all settings as a plain dict."""
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def get_setting(key: str, default: str = "") -> str:
    """Return a single setting value by key."""
    conn = get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def save_setting(key: str, value: str) -> None:
    """Insert or update a single setting."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────────────────────
#  LOGS
# ──────────────────────────────────────────────────────────────

def add_log(username: str, name: str, status: str, error_msg: str = "") -> None:
    """Insert a log entry."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO logs (username, name, status, error_msg) VALUES (?, ?, ?, ?)",
        (username, name, status, error_msg),
    )
    conn.commit()
    conn.close()


def get_all_logs(limit: int = 500) -> list:
    """Return the most recent log entries."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, username, name, status, error_msg, timestamp "
        "FROM logs ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_logs() -> None:
    """Delete all log entries."""
    conn = get_connection()
    conn.execute("DELETE FROM logs")
    conn.commit()
    conn.close()


def reset_session() -> None:
    """Mark session as inactive (called on app startup to clear stale state)."""
    save_setting("session_active", "0")


# Initialize on import
initialize_db()
# Reset session state so a fresh browser open is always required
reset_session()
