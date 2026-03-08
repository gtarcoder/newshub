from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
from bs4 import BeautifulSoup

from newshub.fetchers.base import BaseFetcher
from newshub.models import NewsItem

logger = logging.getLogger(__name__)


class RSSFetcher(BaseFetcher):
    """Fetch news from RSS/Atom feeds."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.feeds: list[dict[str, str]] = config.get("feeds", [])
        self.default_layer: str = config.get("layer", "default")

    async def fetch(self) -> list[NewsItem]:
        items: list[NewsItem] = []
        for feed_cfg in self.feeds:
            name = feed_cfg.get("name", feed_cfg["url"])
            url = feed_cfg["url"]
            layer = feed_cfg.get("layer", self.default_layer)
            try:
                parsed = feedparser.parse(url)
                for entry in parsed.entries:
                    pub_date = self._parse_date(entry)
                    items.append(
                        NewsItem(
                            title=entry.get("title", "").strip(),
                            url=entry.get("link", ""),
                            source="rss",
                            source_name=name,
                            layer=layer,
                            published_at=pub_date,
                            score=self._compute_score(entry, pub_date),
                            summary=self._extract_summary(entry),
                        )
                    )
            except Exception:
                logger.exception("Failed to fetch RSS feed: %s", url)
        return items

    @staticmethod
    def _parse_date(entry: Any) -> datetime | None:
        for field in ("published", "updated"):
            raw = entry.get(field)
            if raw:
                try:
                    return parsedate_to_datetime(raw)
                except Exception:
                    pass
        return None

    @staticmethod
    def _compute_score(entry: Any, pub_date: datetime | None) -> float:
        if pub_date is None:
            return 0.0
        now = datetime.now(timezone.utc)
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)
        age_hours = (now - pub_date).total_seconds() / 3600
        return max(0.0, 100.0 - age_hours)

    @staticmethod
    def _extract_summary(entry: Any) -> str:
        raw = entry.get("summary", "")
        if not raw:
            content = entry.get("content")
            if content and isinstance(content, list):
                raw = content[0].get("value", "")
        if not raw or "<" not in raw:
            text = raw
        else:
            text = BeautifulSoup(raw, "lxml").get_text(separator=" ", strip=True)
        if len(text) > 200:
            text = text[:200] + "…"
        return text
