import sqlite3
from pathlib import Path

_conn: sqlite3.Connection | None = None


def init_db(db_path: str | Path) -> None:
    global _conn
    _conn = sqlite3.connect(str(db_path))
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            chat_id      INTEGER PRIMARY KEY,
            session_uuid TEXT NOT NULL,
            pending_photo TEXT,
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # migrate existing DBs that lack the pending_photo column
    cols = [r[1] for r in _conn.execute("PRAGMA table_info(sessions)").fetchall()]
    if "pending_photo" not in cols:
        _conn.execute("ALTER TABLE sessions ADD COLUMN pending_photo TEXT")
    _conn.commit()


def _db() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("Database not initialised -- call init_db() first")
    return _conn


def get_session(chat_id: int) -> str | None:
    row = (
        _db()
        .execute("SELECT session_uuid FROM sessions WHERE chat_id = ?", (chat_id,))
        .fetchone()
    )
    return row[0] if row else None


def set_session(chat_id: int, session_uuid: str) -> None:
    _db().execute(
        "INSERT INTO sessions (chat_id, session_uuid) VALUES (?, ?)"
        " ON CONFLICT(chat_id) DO UPDATE SET session_uuid = excluded.session_uuid,"
        " created_at = CURRENT_TIMESTAMP",
        (chat_id, session_uuid),
    )
    _db().commit()


def clear_session(chat_id: int) -> None:
    _db().execute("DELETE FROM sessions WHERE chat_id = ?", (chat_id,))
    _db().commit()


def get_pending_photo(chat_id: int) -> str | None:
    row = (
        _db()
        .execute("SELECT pending_photo FROM sessions WHERE chat_id = ?", (chat_id,))
        .fetchone()
    )
    return row[0] if row else None


def set_pending_photo(chat_id: int, path: str | None) -> None:
    _db().execute(
        "INSERT INTO sessions (chat_id, session_uuid, pending_photo) VALUES (?, '', ?)"
        " ON CONFLICT(chat_id) DO UPDATE SET pending_photo = excluded.pending_photo",
        (chat_id, path),
    )
    _db().commit()
