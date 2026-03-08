from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup

from newshub.fetchers.base import BaseFetcher
from newshub.models import NewsItem

logger = logging.getLogger(__name__)

CAIXIN_SCROLL_URL = "https://gateway.caixin.com/api/extapi/homeInterface.jsp"
CAIXIN_ROLL_URL = "https://roll.caixin.com/news/index_1.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.caixin.com/",
}


class CaixinFetcher(BaseFetcher):
    """Fetch news from 财新 (Caixin)."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.layer: str = config.get("layer", "deep")

    async def fetch(self) -> list[NewsItem]:
        items = await self._fetch_via_api()
        if items:
            return items
        return await self._fetch_via_html()

    async def _fetch_via_api(self) -> list[NewsItem]:
        items: list[NewsItem] = []
        params = {"subject": "", "page": 1, "count": 30}
        try:
            async with httpx.AsyncClient(
                timeout=15, headers=HEADERS
            ) as client:
                resp = await client.get(CAIXIN_SCROLL_URL, params=params)
                if resp.status_code != 200:
                    return []
                data = resp.json()

            for entry in data.get("datas", data.get("data", [])):
                title = entry.get("title", "").strip()
                url = entry.get("link", "") or entry.get("url", "")
                if not title or not url:
                    continue

                pub_str = entry.get("time", "") or entry.get("pubTime", "")
                pub_date = self._parse_datetime(pub_str)

                items.append(
                    NewsItem(
                        title=title,
                        url=url,
                        source="caixin",
                        source_name="财新",
                        layer=self.layer,
                        published_at=pub_date,
                        score=self._time_score(pub_date),
                        summary=entry.get("summary", "")[:200],
                    )
                )
        except Exception:
            logger.debug("Caixin API fetch failed", exc_info=True)
        return items

    async def _fetch_via_html(self) -> list[NewsItem]:
        """Fallback: scrape the rolling news page."""
        items: list[NewsItem] = []
        try:
            async with httpx.AsyncClient(
                timeout=15, headers=HEADERS, follow_redirects=True
            ) as client:
                resp = await client.get(CAIXIN_ROLL_URL)
                resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "lxml")
            articles = soup.select("dl.clearfix, ul.newslist li, .neirong a")

            for i, el in enumerate(articles[:30]):
                link = el.select_one("a[href]") if el.name != "a" else el
                if not link:
                    continue
                title = link.get_text(strip=True)
                href = link.get("href", "")
                if not title or not href:
                    continue
                if not href.startswith("http"):
                    href = f"https:{href}" if href.startswith("//") else f"https://www.caixin.com{href}"

                items.append(
                    NewsItem(
                        title=title,
                        url=href,
                        source="caixin",
                        source_name="财新",
                        layer=self.layer,
                        score=max(0.0, 100.0 - i * 3),
                    )
                )
        except Exception:
            logger.exception("Failed to fetch Caixin rolling news")
        return items

    @staticmethod
    def _parse_datetime(s: str) -> datetime | None:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    @staticmethod
    def _time_score(pub_date: datetime | None) -> float:
        if pub_date is None:
            return 0.0
        now = datetime.now(timezone.utc)
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)
        age_hours = (now - pub_date).total_seconds() / 3600
        return max(0.0, 100.0 - age_hours)
