from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from newshub.fetchers.base import BaseFetcher
from newshub.models import NewsItem

logger = logging.getLogger(__name__)

NEWSAPI_URL = "https://newsapi.org/v2/top-headlines"


class NewsAPIFetcher(BaseFetcher):
    """Fetch top headlines from NewsAPI.org."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.api_key: str = config.get("api_key", "")
        self.country: str = config.get("country", "us")
        self.page_size: int = config.get("page_size", 20)
        self.layer: str = config.get("layer", "default")

    async def fetch(self) -> list[NewsItem]:
        if not self.api_key or self.api_key.startswith("${"):
            logger.warning("NewsAPI key not configured, skipping")
            return []

        params = {
            "apiKey": self.api_key,
            "country": self.country,
            "pageSize": self.page_size,
        }
        items: list[NewsItem] = []
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(NEWSAPI_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            for i, article in enumerate(data.get("articles", [])):
                pub_date = self._parse_date(article.get("publishedAt"))
                items.append(
                    NewsItem(
                        title=article.get("title", "").strip(),
                        url=article.get("url", ""),
                        source="newsapi",
                        source_name=article.get("source", {}).get("name", "NewsAPI"),
                        layer=self.layer,
                        published_at=pub_date,
                        score=self._compute_score(pub_date, i),
                        summary=article.get("description", "") or "",
                    )
                )
        except Exception:
            logger.exception("Failed to fetch from NewsAPI")
        return items

    @staticmethod
    def _parse_date(raw: str | None) -> datetime | None:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None

    @staticmethod
    def _compute_score(pub_date: datetime | None, rank: int) -> float:
        """Higher ranked (lower index) articles and newer ones score higher."""
        base = max(0.0, 100.0 - rank * 2)
        if pub_date:
            now = datetime.now(timezone.utc)
            if pub_date.tzinfo is None:
                pub_date = pub_date.replace(tzinfo=timezone.utc)
            age_hours = (now - pub_date).total_seconds() / 3600
            base += max(0.0, 50.0 - age_hours)
        return base
