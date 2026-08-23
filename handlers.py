from __future__ import annotations

import logging

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.errors import RPCError
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from database import ChatSettings, SettingsStore
from models import Track
from player import MusicPlayer
from search import MusicSearcher

logger = logging.getLogger("lybot.handlers")


def register_handlers(
    bot: Client,
    player: MusicPlayer,
    searcher: MusicSearcher,
    settings: SettingsStore,
) -> None:
    player.set_resolver(searcher.resolve_stream)
    pending_searches: dict[int, list[Track]] = {}

    @bot.on_message(filters.command(["start", "help"]))
    async def help_handler(_: Client, message: Message) -> None:
        await message.reply_text(help_text(), disable_web_page_preview=True)

    @bot.on_message(filters.command(["song", "search"]))
    async def search_handler(_: Client, message: Message) -> None:
        query = command_argument(message)
        if not query:
            await message.reply_text("اكتب اسم الأغنية بعد الأمر، مثال:\n/song Skyfall Adele")
            return
        await show_search_results(message, query, searcher, pending_searches)

    @bot.on_message(filters.command(["play", "p", "vplay"]))
    async def play_handler(_: Client, message: Message) -> None:
        if message.chat.type == ChatType.PRIVATE:
            await message.reply_text("أضفني إلى كروب ثم استخدم /play داخل المكالمة الصوتية.")
            return
        query = command_argument(message)
        if not query:
            await message.reply_text("اكتب اسم الأغنية أو الرابط بعد /play.")
            return
        if not await allowed_to_play(message, settings.get(message.chat.id)):
            return
        await play_query(message, query, searcher, player, settings, pending_searches)

    @bot.on_message(filters.command("join"))
    async def join_handler(_: Client, message: Message) -> None:
        if not await require_admin(message):
            return
        try:
            await player.join(message.chat.id)
            await message.reply_text("دخلت للمكالمة الصوتية.")
        except Exception as exc:
            await report_error(message, exc, "تأكد أن هناك مكالمة صوتية وأن الحساب المساعد عضو بالكروب.")

    @bot.on_message(filters.command(["pause", "resume", "continue", "skip", "next", "stop", "end", "queue", "playlist", "now", "current"]))
    async def control_handler(_: Client, message: Message) -> None:
        command = (message.command or [""])[0].lower()
        if command in {"stop", "end"} and not await require_admin(message):
            return
        try:
            if command == "pause":
                track = await player.pause(message.chat.id)
                await message.reply_text(f"تم الإيقاف المؤقت:\n{track.label()}", reply_markup=controls(player, message.chat.id))
            elif command in {"resume", "continue"}:
                track = await player.resume(message.chat.id)
                await message.reply_text(f"تم الاستئناف:\n{track.label()}", reply_markup=controls(player, message.chat.id))
            elif command in {"skip", "next"}:
                old, new = await player.skip(message.chat.id)
                if new:
                    await message.reply_text(f"تم التخطي.\nالتالية: {new.label()}", reply_markup=controls(player, message.chat.id))
                else:
                    await message.reply_text(f"انتهى الطابور.\nتم تخطي: {old.label() if old else 'الأغنية'}")
            elif command in {"stop", "end"}:
                await player.stop(message.chat.id)
                await message.reply_text("تم إيقاف التشغيل وتفريغ الطابور.")
            elif command in {"queue", "playlist"}:
                await send_queue(message, player)
            else:
                await send_now(message, player)
        except Exception as exc:
            await report_error(message, exc)

    @bot.on_message(filters.command("settings"))
    async def settings_handler(_: Client, message: Message) -> None:
        if message.chat.type == ChatType.PRIVATE:
            await message.reply_text("الإعدادات متاحة داخل الكروبات فقط.")
            return
        if not await require_admin(message):
            return
        await message.reply_text(
            settings_text(settings.get(message.chat.id)),
            reply_markup=settings_keyboard(message.chat.id, settings.get(message.chat.id)),
        )

    @bot.on_callback_query()
    async def callback_handler(_: Client, query: CallbackQuery) -> None:
        if not query.message:
            await query.answer()
            return
        try:
            await handle_callback(query, player, settings, pending_searches)
        except Exception as exc:
            logger.exception("Callback failed")
            await query.answer("صار خطأ، حاول مرة ثانية", show_alert=True)
            await report_error(query.message, exc)


def help_text() -> str:
    return (
        "🎵 LyBot — بوت الميوزك للكروبات\n\n"
        "التشغيل:\n"
        "/play اسم الأغنية أو الرابط\n"
        "/p اسم الأغنية\n"
        "/vplay اسم الأغنية\n"
        "/song اسم الأغنية — بحث بدون تشغيل\n"
        "/join — دخول المكالمة\n\n"
        "التحكم:\n"
        "/pause /resume\n"
        "/skip أو /next\n"
        "/stop أو /end\n"
        "/queue — عرض الطابور\n"
        "/now — الأغنية الحالية\n\n"
        "/settings — إعدادات الكروب"
    )


def command_argument(message: Message) -> str:
    if not message.command:
        return ""
    return " ".join(message.command[1:]).strip()


async def show_search_results(
    message: Message,
    query: str,
    searcher: MusicSearcher,
    pending_searches: dict[int, list[Track]],
) -> None:
    status = await message.reply_text("أبحث لك عن أفضل النتائج...")
    results = await searcher.search(query, requested_by=display_user(message))
    if not results:
        await status.edit_text("ما لكيت نتائج مناسبة. جرب اسم الفنان ويا اسم الأغنية.")
        return
    pending_searches[status.id] = results
    await status.edit_text(
        format_results(results, query),
        reply_markup=search_keyboard(results),
        disable_web_page_preview=True,
    )


async def play_query(
    message: Message,
    query: str,
    searcher: MusicSearcher,
    player: MusicPlayer,
    settings: SettingsStore,
    pending_searches: dict[int, list[Track]],
) -> None:
    status = await message.reply_text("أدور على أفضل نسخة وأجهزها للتشغيل...")
    results = await searcher.search(query, requested_by=display_user(message))
    if not results:
        await status.edit_text("ما لكيت نتيجة. جرب كتابة اسم الفنان والأغنية بشكل أوضح.")
        return
    # Give the user a choice when the query is ambiguous; direct URLs play now.
    if len(results) > 1 and not query.startswith(("http://", "https://")):
        pending_searches[status.id] = results
        await status.edit_text(
            format_results(results, query),
            reply_markup=search_keyboard(results, play_now=True),
            disable_web_page_preview=True,
        )
        return
    await enqueue_and_announce(status, results[0], player, settings)


async def enqueue_and_announce(
    message: Message,
    track: Track,
    player: MusicPlayer,
    settings: SettingsStore,
) -> None:
    try:
        player.set_autoplay(message.chat.id, settings.get(message.chat.id).autoplay)
        started, selected = await player.add(message.chat.id, track)
    except Exception as exc:
        await report_error(message, exc, "تأكد أن الحساب المساعد عضو بالكروب وموجود بالمكالمة.")
        return
    if started:
        text = f"شغلتها هسه:\n{selected.label()}\nالمدة: {selected.duration_text()}"
    else:
        position = len(player.queue(message.chat.id))
        text = f"انضافت للطابور (المركز {position}):\n{selected.label()}"
    await message.edit_text(text, reply_markup=controls(player, message.chat.id))


def search_keyboard(results: list[Track], play_now: bool = False) -> InlineKeyboardMarkup:
    rows = []
    for index, track in enumerate(results[:8]):
        action = "play" if play_now else "pick"
        rows.append(
            [
                InlineKeyboardButton(
                    f"{index + 1}. {track.title[:38]}",
                    callback_data=f"music:{action}:{index}",
                )
            ]
        )
    return InlineKeyboardMarkup(rows)


def controls(player: MusicPlayer, chat_id: int) -> InlineKeyboardMarkup:
    state = "resume" if player.paused(chat_id) else "pause"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("إيقاف مؤقت" if state == "pause" else "استئناف", callback_data=f"control:{state}"),
                InlineKeyboardButton("تخطي", callback_data="control:skip"),
            ],
            [
                InlineKeyboardButton("الطابور", callback_data="control:queue"),
                InlineKeyboardButton("إنهاء", callback_data="control:stop"),
            ],
        ]
    )


async def handle_callback(
    query: CallbackQuery,
    player: MusicPlayer,
    settings: SettingsStore,
    pending_searches: dict[int, list[Track]],
) -> None:
    data = query.data or ""
    await query.answer()
    if data.startswith("music:"):
        _, action, index_text = data.split(":", 2)
        try:
            selected = pending_searches[query.message.id][int(index_text)]
        except (KeyError, IndexError, ValueError):
            await query.message.edit_text("انتهت صلاحية نتائج البحث، استخدم /play مرة ثانية.")
            return
        if action not in {"pick", "play"}:
            return
        selected.requested_by = query.from_user.first_name
        if action == "pick":
            await query.message.edit_text(
                f"النتيجة المختارة:\n{selected.label()}\n"
                f"المدة: {selected.duration_text()}\n"
                f"الرابط: {selected.webpage_url}\n\n"
                "إذا تريد تشغيلها استخدم /play مع اسمها.",
                disable_web_page_preview=True,
            )
            return
        await enqueue_and_announce(query.message, selected, player, settings)
        return
    if data.startswith("control:"):
        action = data.split(":", 1)[1]
        fake_message = query.message
        if action == "pause":
            await player.pause(fake_message.chat.id)
        elif action == "resume":
            await player.resume(fake_message.chat.id)
        elif action == "skip":
            await player.skip(fake_message.chat.id)
        elif action == "stop":
            if not await require_admin(fake_message, query.from_user.id):
                return
            await player.stop(fake_message.chat.id)
            await fake_message.edit_text("تم إنهاء التشغيل.")
            return
        elif action == "queue":
            await send_queue(fake_message, player)
            return
        await fake_message.edit_reply_markup(controls(player, fake_message.chat.id))
        return
    if data.startswith("setting:"):
        if not await require_admin(query.message, query.from_user.id):
            return
        key = data.split(":", 1)[1]
        settings_now = settings.toggle(query.message.chat.id, key)
        await query.message.edit_text(
            settings_text(settings_now),
            reply_markup=settings_keyboard(query.message.chat.id, settings_now),
        )


async def send_queue(message: Message, player: MusicPlayer) -> None:
    current = player.current(message.chat.id)
    upcoming = player.queue(message.chat.id)
    if current is None:
        await message.reply_text("الطابور فارغ.")
        return
    lines = [f"قيد التشغيل:\n{current.label()}"]
    if upcoming:
        lines.append("\nالتالي:")
        lines.extend(f"{i}. {track.label()}" for i, track in enumerate(upcoming, 1))
    else:
        lines.append("\nماكو أغاني إضافية بالطابور.")
    await message.reply_text("\n".join(lines), reply_markup=controls(player, message.chat.id))


async def send_now(message: Message, player: MusicPlayer) -> None:
    current = player.current(message.chat.id)
    if current is None:
        await message.reply_text("ماكو أغنية قيد التشغيل.")
        return
    await message.reply_text(
        f"الأغنية الحالية:\n{current.label()}\nالمدة: {current.duration_text()}",
        reply_markup=controls(player, message.chat.id),
    )


def format_results(results: list[Track], query: str) -> str:
    lines = [f"نتائج البحث عن: {query}", "اختار النسخة اللي تريدها:"]
    for i, track in enumerate(results, 1):
        lines.append(f"{i}. {track.label()} [{track.duration_text()}]")
    return "\n".join(lines)


def settings_text(value: ChatSettings) -> str:
    return (
        "إعدادات LyBot للكروب\n\n"
        f"التشغيل للأدمن فقط: {'مفعل' if value.admin_only else 'معطل'}\n"
        f"إشعارات التشغيل: {'مفعلة' if value.announce else 'معطلة'}\n"
        f"التشغيل التلقائي من الطابور: {'مفعل' if value.autoplay else 'معطل'}"
    )


def settings_keyboard(chat_id: int, value: ChatSettings) -> InlineKeyboardMarkup:
    def label(name: str, enabled: bool) -> str:
        return f"{'إيقاف' if enabled else 'تفعيل'} {name}"

    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(label("وضع الأدمن", value.admin_only), callback_data="setting:admin_only")],
            [InlineKeyboardButton(label("الإشعارات", value.announce), callback_data="setting:announce")],
            [InlineKeyboardButton(label("التشغيل التلقائي", value.autoplay), callback_data="setting:autoplay")],
        ]
    )


async def allowed_to_play(message: Message, value: ChatSettings) -> bool:
    if not value.admin_only:
        return True
    return await require_admin(message)


async def require_admin(message: Message, user_id: int | None = None) -> bool:
    if message.chat.type == ChatType.PRIVATE:
        return True
    try:
        member = await message._client.get_chat_member(
            message.chat.id,
            user_id or (message.from_user.id if message.from_user else 0),
        )
        if member.status not in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}:
            await message.reply_text("هذا الأمر متاح للمشرفين فقط.")
            return False
        return True
    except RPCError:
        await message.reply_text("ما قدرت أتحقق من صلاحياتك، تأكد أن البوت مشرف بالكروب.")
        return False


async def report_error(message: Message, exc: Exception, hint: str = "") -> None:
    logger.warning("User-facing error: %s", exc)
    detail = hint or "تأكد من وجود الحساب المساعد داخل الكروب ومنح البوت صلاحية إدارة الرسائل."
    await message.reply_text(f"ما كدرت أنفذ الطلب.\n{detail}")


def display_user(message: Message) -> str:
    user = message.from_user
    return user.first_name if user else "unknown"