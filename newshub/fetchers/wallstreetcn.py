from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from newshub.fetchers.base import BaseFetcher
from newshub.models import NewsItem

logger = logging.getLogger(__name__)

LIVES_URL = "https://api-one-wscn.awtmt.com/apiv1/content/lives"
ARTICLES_URL = "https://api-one-wscn.awtmt.com/apiv1/content/articles"


class WallStreetCNFetcher(BaseFetcher):
    """Fetch flash news and articles from 华尔街见闻 (WallStreetCN)."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.limit: int = config.get("limit", 50)
        self.layer: str = config.get("layer", "breaking")

    async def fetch(self) -> list[NewsItem]:
        items: list[NewsItem] = []
        items.extend(await self._fetch_lives())
        items.extend(await self._fetch_articles())
        return items

    async def _fetch_lives(self) -> list[NewsItem]:
        """Fetch real-time flash news (7x24 快讯)."""
        items: list[NewsItem] = []
        params = {"channel": "global-channel", "limit": self.limit}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(LIVES_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            for entry in data.get("data", {}).get("items", []):
                title = entry.get("title", "").strip()
                content_text = entry.get("content_text", "").strip()
                if not title and content_text:
                    title = content_text[:80]
                if not title:
                    continue

                ts = entry.get("display_time", 0)
                pub_date = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
                uri = entry.get("uri", "")
                url = uri if uri.startswith("http") else f"https://wallstreetcn.com/livenews/{uri}" if uri else ""

                items.append(
                    NewsItem(
                        title=title,
                        url=url,
                        source="wallstreetcn",
                        source_name="华尔街见闻·快讯",
                        layer=self.layer,
                        published_at=pub_date,
                        score=self._time_score(pub_date),
                        summary=content_text[:200] if content_text != title else "",
                    )
                )
        except Exception:
            logger.exception("Failed to fetch WallStreetCN lives")
        return items

    async def _fetch_articles(self) -> list[NewsItem]:
        """Fetch top articles."""
        items: list[NewsItem] = []
        params = {"limit": 20}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(ARTICLES_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            for entry in data.get("data", {}).get("items", []):
                title = entry.get("title", "").strip()
                if not title:
                    continue

                ts = entry.get("display_time", 0)
                pub_date = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
                uri = entry.get("uri", "")
                url = uri if uri.startswith("http") else f"https://wallstreetcn.com/articles/{uri}" if uri else ""

                items.append(
                    NewsItem(
                        title=title,
                        url=url,
                        source="wallstreetcn",
                        source_name="华尔街见闻",
                        layer=self.layer,
                        published_at=pub_date,
                        score=self._time_score(pub_date),
                        summary=entry.get("content_short", "")[:200],
                    )
                )
        except Exception:
            logger.exception("Failed to fetch WallStreetCN articles")
        return items

    @staticmethod
    def _time_score(pub_date: datetime | None) -> float:
        if pub_date is None:
            return 0.0
        now = datetime.now(timezone.utc)
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)
        age_hours = (now - pub_date).total_seconds() / 3600
        return max(0.0, 100.0 - age_hours * 2)
