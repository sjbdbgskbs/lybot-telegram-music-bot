from __future__ import annotations

import inspect
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable

from pyrogram import Client
from pytgcalls import filters as call_filters
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
from pytgcalls.types import StreamEnded

from models import QueueState, Track


class MusicPlayer:
    def __init__(
        self,
        assistant: Client,
        max_queue_size: int,
        logger: logging.Logger,
    ) -> None:
        self.assistant = assistant
        self.calls = PyTgCalls(assistant)
        self.max_queue_size = max_queue_size
        self.logger = logger
        self.states: dict[int, QueueState] = defaultdict(QueueState)
        self.autoplay: dict[int, bool] = defaultdict(lambda: True)

    def start(self) -> None:
        @self.calls.on_update(call_filters.stream_end())
        async def stream_end_handler(_: PyTgCalls, update: StreamEnded) -> None:
            await self._handle_stream_end(update.chat_id)

        self.calls.start()

    async def _call(self, method: str, *args: object) -> object:
        result = getattr(self.calls, method)(*args)
        if inspect.isawaitable(result):
            return await result
        return result

    async def add(self, chat_id: int, track: Track) -> tuple[bool, Track | None]:
        state = self.states[chat_id]
        if state.current is None:
            state.current = track
            try:
                await self._play_current(chat_id)
                return True, track
            except Exception:
                state.clear()
                raise
        if len(state.items) >= self.max_queue_size:
            raise RuntimeError(f"الطابور ممتلئ، الحد الأقصى {self.max_queue_size} أغنية")
        state.items.append(track)
        return False, track

    async def _play_current(self, chat_id: int) -> Track:
        state = self.states[chat_id]
        if state.current is None:
            raise RuntimeError("لا توجد أغنية للتشغيل")
        try:
            stream = await self._resolve(state.current)
            await self._call(
                "play",
                chat_id,
                MediaStream(stream.stream_url, video_flags=MediaStream.Flags.IGNORE),
            )
            state.current = stream
            state.paused = False
            return stream
        except Exception:
            self.logger.exception("Could not play in chat %s", chat_id)
            raise

    async def _handle_stream_end(self, chat_id: int) -> None:
        state = self.states[chat_id]
        if state.current is None:
            return
        if not self.autoplay[chat_id] or not state.items:
            state.current = None
            state.paused = False
            if not self.autoplay[chat_id]:
                state.items.clear()
            return
        state.current = state.items.pop(0)
        try:
            await self._play_current(chat_id)
        except Exception:
            self.logger.exception("Could not autoplay next track in chat %s", chat_id)
            state.clear()

    async def _resolve(self, track: Track) -> Track:
        # Searcher is injected lazily by handlers using set_resolver.
        if self.resolver is None:
            raise RuntimeError("Audio resolver is not configured")
        return await self.resolver(track)

    resolver: Callable[[Track], Awaitable[Track]] | None = None

    def set_resolver(self, resolver: Callable[[Track], Awaitable[Track]]) -> None:
        self.resolver = resolver

    def set_autoplay(self, chat_id: int, enabled: bool) -> None:
        self.autoplay[chat_id] = enabled

    async def pause(self, chat_id: int) -> Track:
        state = self._require_current(chat_id)
        await self._call("pause", chat_id)
        state.paused = True
        return state.current  # type: ignore[return-value]

    async def resume(self, chat_id: int) -> Track:
        state = self._require_current(chat_id)
        await self._call("resume", chat_id)
        state.paused = False
        return state.current  # type: ignore[return-value]

    async def skip(self, chat_id: int) -> tuple[Track | None, Track | None]:
        state = self._require_current(chat_id)
        old = state.current
        state.current = state.items.pop(0) if state.items else None
        state.paused = False
        if state.current is None:
            await self._call("leave_call", chat_id)
            return old, None
        await self._play_current(chat_id)
        return old, state.current

    async def stop(self, chat_id: int) -> None:
        state = self.states[chat_id]
        try:
            await self._call("leave_call", chat_id)
        finally:
            state.clear()

    async def join(self, chat_id: int) -> None:
        await self._call("join_group_call", chat_id)

    def current(self, chat_id: int) -> Track | None:
        return self.states[chat_id].current

    def queue(self, chat_id: int) -> list[Track]:
        return list(self.states[chat_id].items)

    def paused(self, chat_id: int) -> bool:
        return self.states[chat_id].paused

    def _require_current(self, chat_id: int) -> QueueState:
        state = self.states[chat_id]
        if state.current is None:
            raise RuntimeError("ماكو أغنية قيد التشغيل حالياً")
        return state

    async def shutdown(self) -> None:
        for chat_id in list(self.states):
            try:
                await self.stop(chat_id)
            except Exception:
                self.logger.exception("Could not stop call in chat %s", chat_id)
        stop_result = self.calls.stop()
        if inspect.isawaitable(stop_result):
            await stop_result