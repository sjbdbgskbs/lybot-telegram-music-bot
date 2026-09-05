from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Copy .env.example to .env and configure it."
        )
    return value


@dataclass(frozen=True)
class Settings:
    bot_token: str
    api_id: int
    api_hash: str
    database_path: str
    max_queue_size: int
    search_results: int
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            api_id = int(required("TELEGRAM_API_ID"))
        except ValueError as exc:
            raise RuntimeError("TELEGRAM_API_ID must be a number") from exc

        return cls(
            bot_token=required("TELEGRAM_BOT_TOKEN"),
            api_id=api_id,
            api_hash=required("TELEGRAM_API_HASH"),
            database_path=os.getenv("DATABASE_PATH", "data/lybot.sqlite3"),
            max_queue_size=max(1, int(os.getenv("MAX_QUEUE_SIZE", "50"))),
            search_results=max(3, min(10, int(os.getenv("SEARCH_RESULTS", "8")))),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )