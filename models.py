from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Track:
    title: str
    url: str
    webpage_url: str
    source: str
    duration: int | None = None
    uploader: str = ""
    thumbnail: str = ""
    requested_by: str = ""
    search_score: float = 0.0
    stream_url: str = ""

    @classmethod
    def from_ytdlp(cls, item: dict[str, Any], requested_by: str = "") -> "Track":
        webpage_url = item.get("webpage_url") or item.get("original_url") or item.get("url") or ""
        source = (item.get("extractor_key") or item.get("extractor") or "web").lower()
        return cls(
            title=(item.get("title") or "Unknown title").strip(),
            url=webpage_url,
            webpage_url=webpage_url,
            source=source,
            duration=int(item["duration"]) if item.get("duration") else None,
            uploader=(item.get("uploader") or item.get("artist") or "").strip(),
            thumbnail=item.get("thumbnail") or "",
            requested_by=requested_by,
        )

    def duration_text(self) -> str:
        if not self.duration:
            return "غير معروف"
        minutes, seconds = divmod(self.duration, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def label(self) -> str:
        artist = f" — {self.uploader}" if self.uploader else ""
        return f"{self.title}{artist}"


@dataclass
class QueueState:
    current: Track | None = None
    items: list[Track] = field(default_factory=list)
    paused: bool = False

    def clear(self) -> None:
        self.current = None
        self.items.clear()
        self.paused = False