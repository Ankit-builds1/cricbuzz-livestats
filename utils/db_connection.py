# © 2026 Ankit Dash (github.com/Ankit-builds1) - Cricbuzz LiveStats. All rights reserved.
"""Centralised database connection handling for Cricbuzz LiveStats."""
import math
import os
import sqlite3
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "data" / "cricbuzz.db"))
SCHEMA_PATH = BASE_DIR / "sql" / "schema.sql"


def get_connection():
    """Return a SQLite connection with foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    # SQLite has no built-in SQRT on every build; needed for std-dev (Q19, Q23)
    conn.create_function("SQRT", 1, lambda x: math.sqrt(x) if x is not None and x >= 0 else None)
    return conn


def init_db():
    """Create all tables from sql/schema.sql if they don't exist."""
    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def run_query(sql, params=()):
    """Run a SELECT query and return the result as a pandas DataFrame."""
    try:
        with get_connection() as conn:
            return pd.read_sql_query(sql, conn, params=params)
    except Exception as e:  # surface DB errors to the UI instead of crashing
        raise RuntimeError(f"Query failed: {e}") from e


def execute(sql, params=()):
    """Run an INSERT/UPDATE/DELETE and commit. Returns rows affected."""
    with get_connection() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.rowcount


if __name__ == "__main__":
    init_db()
    tables = run_query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    print("Database created at:", DB_PATH)
    print("Tables:", ", ".join(tables["name"]))
