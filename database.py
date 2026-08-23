from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class ChatSettings:
    admin_only: bool = False
    announce: bool = True
    autoplay: bool = True
    max_queue: int = 50


class SettingsStore:
    def __init__(self, path: str) -> None:
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = Lock()
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id INTEGER PRIMARY KEY,
                admin_only INTEGER NOT NULL DEFAULT 0,
                announce INTEGER NOT NULL DEFAULT 1,
                autoplay INTEGER NOT NULL DEFAULT 1,
                max_queue INTEGER NOT NULL DEFAULT 50
            )
            """
        )
        self.connection.commit()

    def get(self, chat_id: int) -> ChatSettings:
        with self.lock:
            row = self.connection.execute(
                "SELECT admin_only, announce, autoplay, max_queue "
                "FROM chat_settings WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
        if row is None:
            return ChatSettings()
        return ChatSettings(
            admin_only=bool(row["admin_only"]),
            announce=bool(row["announce"]),
            autoplay=bool(row["autoplay"]),
            max_queue=int(row["max_queue"]),
        )

    def toggle(self, chat_id: int, key: str) -> ChatSettings:
        allowed = {"admin_only", "announce", "autoplay"}
        if key not in allowed:
            raise ValueError(f"Unsupported setting: {key}")
        current = self.get(chat_id)
        value = not getattr(current, key)
        with self.lock:
            self.connection.execute(
                f"""
                INSERT INTO chat_settings (chat_id, {key})
                VALUES (?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET {key} = excluded.{key}
                """,
                (chat_id, int(value)),
            )
            self.connection.commit()
        return self.get(chat_id)

    def close(self) -> None:
        with self.lock:
            self.connection.close()