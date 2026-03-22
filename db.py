import sqlite3
from datetime import datetime, timedelta
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
    _conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cron_jobs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id      INTEGER NOT NULL,
            fire_at_time TEXT NOT NULL,
            repeat       TEXT DEFAULT 'once',
            is_claude    INTEGER DEFAULT 0,
            message      TEXT NOT NULL,
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            next_fire    TEXT NOT NULL
        )
        """
    )
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


# ── cron jobs ──


def add_cron_job(
    chat_id: int,
    fire_at_time: str,
    message: str,
    repeat: str = "once",
    is_claude: bool = False,
    next_fire: str | None = None,
) -> int:
    if next_fire is None:
        next_fire = _compute_next_fire(fire_at_time)
    cur = _db().execute(
        "INSERT INTO cron_jobs (chat_id, fire_at_time, repeat, is_claude, message, next_fire)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (chat_id, fire_at_time, repeat, int(is_claude), message, next_fire),
    )
    _db().commit()
    return cur.lastrowid


def get_cron_jobs(chat_id: int) -> list[dict]:
    rows = (
        _db()
        .execute(
            "SELECT id, fire_at_time, repeat, is_claude, message, next_fire"
            " FROM cron_jobs WHERE chat_id = ? ORDER BY next_fire",
            (chat_id,),
        )
        .fetchall()
    )
    return [
        {
            "id": r[0],
            "fire_at_time": r[1],
            "repeat": r[2],
            "is_claude": bool(r[3]),
            "message": r[4],
            "next_fire": r[5],
        }
        for r in rows
    ]


def get_due_jobs(now_iso: str) -> list[dict]:
    rows = (
        _db()
        .execute(
            "SELECT id, chat_id, fire_at_time, repeat, is_claude, message"
            " FROM cron_jobs WHERE next_fire <= ?",
            (now_iso,),
        )
        .fetchall()
    )
    return [
        {
            "id": r[0],
            "chat_id": r[1],
            "fire_at_time": r[2],
            "repeat": r[3],
            "is_claude": bool(r[4]),
            "message": r[5],
        }
        for r in rows
    ]


def delete_cron_job(job_id: int) -> None:
    _db().execute("DELETE FROM cron_jobs WHERE id = ?", (job_id,))
    _db().commit()


def update_next_fire(job_id: int, next_iso: str) -> None:
    _db().execute(
        "UPDATE cron_jobs SET next_fire = ? WHERE id = ?", (next_iso, job_id)
    )
    _db().commit()


def _compute_next_fire(fire_at_time: str) -> str:
    now = datetime.now()
    hour, minute = map(int, fire_at_time.split(":"))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target.isoformat()
