from __future__ import annotations

import asyncio
import logging

from pyrogram import Client, idle

from config import Settings
from handlers import register_handlers
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
    register_handlers(bot=bot, searcher=searcher)

    logger.info("Starting LyBot services")
    await bot.start()
    me = await bot.get_me()
    logger.info("Bot started as @%s", me.username or me.id)

    try:
        await idle()
    finally:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())