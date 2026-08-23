from __future__ import annotations

import asyncio
import logging
import re
from difflib import SequenceMatcher
from urllib.parse import urlparse

import yt_dlp

from models import Track


class MusicSearcher:
    SEARCHERS = ("ytsearch", "scsearch", "bcsearch")

    def __init__(self, max_results: int, logger: logging.Logger) -> None:
        self.max_results = max_results
        self.logger = logger

    async def search(self, query: str, requested_by: str = "") -> list[Track]:
        return await asyncio.to_thread(self._search_sync, query, requested_by)

    async def resolve_stream(self, track: Track) -> Track:
        return await asyncio.to_thread(self._resolve_stream_sync, track)

    def _search_sync(self, query: str, requested_by: str) -> list[Track]:
        query = query.strip()
        if not query:
            return []

        direct_url = self._is_url(query)
        if direct_url:
            candidates = self._extract(query, requested_by)
        else:
            candidates = []
            for prefix in self.SEARCHERS:
                candidates.extend(
                    self._extract(f"{prefix}{self.max_results}:{query}", requested_by)
                )

            # Spotify and Apple Music links usually expose metadata but not a
            # playable stream. Search the metadata title on public sources.
        if direct_url and not candidates:
            fallback_query = self._metadata_query(query)
            if fallback_query:
                candidates = self._extract(f"ytsearch{self.max_results}:{fallback_query}", requested_by)

        unique: dict[str, Track] = {}
        for track in candidates:
            key = self._normalise(f"{track.title} {track.uploader}")
            if key and key not in unique:
                unique[key] = track

        results = list(unique.values())
        for track in results:
            track.search_score = self._score(query, track)
        results.sort(key=lambda item: item.search_score, reverse=True)
        return results[: self.max_results]

    def _extract(self, target: str, requested_by: str) -> list[Track]:
        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
            "noplaylist": True,
            "playlistend": self.max_results,
            "default_search": "auto",
        }
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(target, download=False)
        except Exception as exc:
            self.logger.warning("Search failed for %s: %s", target[:80], exc)
            return []

        entries = info.get("entries") if isinstance(info, dict) else None
        raw_items = [item for item in (entries or [info]) if item]
        return [Track.from_ytdlp(item, requested_by) for item in raw_items]

    def _resolve_stream_sync(self, track: Track) -> Track:
        target = track.webpage_url or track.url
        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "bestaudio[acodec!=none]/bestaudio/best",
            "outtmpl": "-",
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(target, download=False)
        track.stream_url = info.get("url", "")
        track.duration = track.duration or info.get("duration")
        track.title = info.get("title") or track.title
        track.uploader = info.get("uploader") or track.uploader
        if not track.stream_url:
            raise RuntimeError("The selected source did not return an audio stream")
        return track

    @staticmethod
    def _is_url(value: str) -> bool:
        try:
            parsed = urlparse(value)
            return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
        except ValueError:
            return False

    @staticmethod
    def _metadata_query(value: str) -> str:
        host = urlparse(value).netloc.lower()
        if "spotify" in host or "apple" in host or "music.apple" in host:
            return value.rsplit("/", 1)[-1].replace("-", " ")
        return ""

    @staticmethod
    def _normalise(value: str) -> str:
        value = value.lower()
        value = re.sub(r"\([^)]*\)|\[[^]]*\]", " ", value)
        value = re.sub(r"[^a-z0-9\u0600-\u06ff]+", " ", value)
        return re.sub(r"\s+", " ", value).strip()

    def _score(self, query: str, track: Track) -> float:
        wanted = self._normalise(query)
        title = self._normalise(track.title)
        artist = self._normalise(track.uploader)
        combined = f"{title} {artist}".strip()
        ratio = SequenceMatcher(None, wanted, combined).ratio()
        wanted_words = set(wanted.split())
        result_words = set(combined.split())
        overlap = len(wanted_words & result_words) / max(len(wanted_words), 1)
        source_bonus = {"youtube": 0.08, "soundcloud": 0.06, "bandcamp": 0.04}.get(
            track.source, 0.0
        )
        duration_bonus = 0.03 if track.duration and track.duration >= 30 else 0.0
        return ratio * 0.55 + overlap * 0.42 + source_bonus + duration_bonus