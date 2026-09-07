import sqlite3
from pathlib import Path

from kivi.config import DB_PATH

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(reset: bool = False) -> None:
    """Apply migrations in order. If reset, drop the DB file first."""
    if reset and Path(DB_PATH).exists():
        Path(DB_PATH).unlink()

    conn = get_connection()
    try:
        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            conn.executescript(migration.read_text())
        conn.commit()
    finally:
        conn.close()
