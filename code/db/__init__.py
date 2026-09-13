"""
DB connection singleton.
Usage:
    from code.db import get_db
    conn = get_db()
"""
import sqlite3
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_DB_PATH = os.getenv("DATABASE_URL", "./spendly.db")
_conn: sqlite3.Connection | None = None


def get_db() -> sqlite3.Connection:
    """Return a shared SQLite connection (row_factory = sqlite3.Row)."""
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
    return _conn


def init_schema():
    """Create all tables from schema.sql if they don't exist."""
    schema_path = Path(__file__).parent / "schema.sql"
    conn = get_db()
    conn.executescript(schema_path.read_text())
    conn.commit()
