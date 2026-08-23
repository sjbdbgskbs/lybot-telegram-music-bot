from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from pyrogram import Client, idle

from config import Settings
from database import SettingsStore
from handlers import register_handlers
from player import MusicPlayer
from search import MusicSearcher


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


async def main() -> None:
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    logger = logging.getLogger("lybot")

    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    store = SettingsStore(settings.database_path)
    searcher = MusicSearcher(
        max_results=settings.search_results,
        logger=logging.getLogger("lybot.search"),
    )

    bot = Client(
        "lybot-bot",
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        bot_token=settings.bot_token,
        in_memory=True,
    )
    assistant = Client(
        "lybot-assistant",
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        session_string=settings.user_session,
        in_memory=True,
    )

    player = MusicPlayer(
        assistant=assistant,
        max_queue_size=settings.max_queue_size,
        logger=logging.getLogger("lybot.player"),
    )
    register_handlers(
        bot=bot,
        player=player,
        searcher=searcher,
        settings=store,
    )

    logger.info("Starting LyBot services")
    await bot.start()
    await assistant.start()
    player.start()
    me = await bot.get_me()
    logger.info("Bot started as @%s", me.username or me.id)

    try:
        await idle()
    finally:
        await player.shutdown()
        await assistant.stop()
        await bot.stop()
        store.close()


if __name__ == "__main__":
    asyncio.run(main())