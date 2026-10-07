import os
import sqlite3
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def _db_path() -> Path:
    return Path(os.environ.get("SNAPSHOT_DB", "data/snapshots.sqlite3"))


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS snapshots (key TEXT PRIMARY KEY, payload TEXT NOT NULL)")
    return conn


def save_snapshot(key: str, model: BaseModel) -> None:
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO snapshots (key, payload) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET payload = excluded.payload",
                (key, model.model_dump_json()),
            )
    except (sqlite3.Error, OSError):
        pass


def load_snapshot(key: str, model_type: type[T]) -> T | None:
    try:
        with _connect() as conn:
            row = conn.execute("SELECT payload FROM snapshots WHERE key = ?", (key,)).fetchone()
    except (sqlite3.Error, OSError):
        return None
    if row is None:
        return None
    try:
        return model_type.model_validate_json(row[0])
    except ValueError:
        return None