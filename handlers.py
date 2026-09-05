from __future__ import annotations

import logging

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from models import Track
from search import MusicSearcher

logger = logging.getLogger("lybot.handlers")


def register_handlers(bot: Client, searcher: MusicSearcher) -> None:
    pending_searches: dict[int, list[Track]] = {}

    @bot.on_message(filters.command(["start", "help"]))
    async def help_handler(_: Client, message: Message) -> None:
        await message.reply_text(help_text(), disable_web_page_preview=True)

    @bot.on_message(filters.command(["play", "p", "vplay", "song", "search"]))
    async def search_handler(_: Client, message: Message) -> None:
        query = command_argument(message)
        if not query:
            await message.reply_text(
                "اكتب اسم الأغنية أو الرابط بعد الأمر.\n"
                "مثال: /play Skyfall Adele"
            )
            return
        status = await message.reply_text("أبحث عن أفضل النتائج...")
        results = await searcher.search(query, requested_by=display_user(message))
        if not results:
            await status.edit_text("ما لكيت نتائج مناسبة. جرب اسم الفنان ويا اسم الأغنية.")
            return
        pending_searches[status.id] = results
        await status.edit_text(
            format_results(results, query),
            reply_markup=results_keyboard(results),
            disable_web_page_preview=True,
        )

    @bot.on_message(filters.command(["pause", "resume", "continue", "skip", "next", "stop", "end", "queue", "playlist", "now", "current", "join"]))
    async def removed_voice_commands(_: Client, message: Message) -> None:
        await message.reply_text(
            "ميزة المكالمات الصوتية أزيلت من هذه النسخة.\n"
            "استخدم /play للبحث عن الأغاني والروابط."
        )

    @bot.on_message(filters.command("settings"))
    async def settings_handler(_: Client, message: Message) -> None:
        await message.reply_text(
            "هذه النسخة تعمل كبوت بحث وروابط فقط، ولا تستخدم المكالمات الصوتية."
        )

    @bot.on_callback_query()
    async def callback_handler(_: Client, query: CallbackQuery) -> None:
        if not query.message:
            await query.answer()
            return
        data = query.data or ""
        if not data.startswith("result:"):
            await query.answer()
            return
        try:
            index = int(data.split(":", 1)[1])
            track = pending_searches[query.message.id][index]
        except (KeyError, IndexError, ValueError):
            await query.answer("انتهت صلاحية النتائج، أرسل الأمر من جديد.", show_alert=True)
            return
        await query.answer()
        await query.message.edit_text(
            selected_result_text(track),
            disable_web_page_preview=True,
        )


def help_text() -> str:
    return (
        "LyBot — بوت بحث الأغاني\n\n"
        "/play اسم الأغنية أو الرابط\n"
        "/p اسم الأغنية — اختصار\n"
        "/vplay اسم الأغنية — اختصار\n"
        "/song اسم الأغنية — بحث\n"
        "/search اسم الأغنية — بحث\n\n"
        "اضغط على النتيجة حتى يظهر لك الرابط المناسب.\n"
        "ميزة التشغيل داخل المكالمات الصوتية غير موجودة في هذه النسخة."
    )


def command_argument(message: Message) -> str:
    if not message.command:
        return ""
    return " ".join(message.command[1:]).strip()


def results_keyboard(results: list[Track]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"{index + 1}. {track.title[:40]}",
                    callback_data=f"result:{index}",
                )
            ]
            for index, track in enumerate(results[:8])
        ]
    )


def format_results(results: list[Track], query: str) -> str:
    lines = [f"نتائج البحث عن: {query}", "اختار النتيجة حتى يظهر الرابط:"]
    for index, track in enumerate(results, 1):
        lines.append(
            f"{index}. {track.label()} [{track.duration_text()}] "
            f"({track.source})"
        )
    return "\n".join(lines)


def selected_result_text(track: Track) -> str:
    return (
        f"النتيجة المختارة:\n{track.label()}\n"
        f"المدة: {track.duration_text()}\n"
        f"المصدر: {track.source}\n\n"
        f"{track.webpage_url}"
    )


def display_user(message: Message) -> str:
    user = message.from_user
    return user.first_name if user else "unknown"