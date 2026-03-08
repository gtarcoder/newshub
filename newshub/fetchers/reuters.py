from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup

from newshub.fetchers.base import BaseFetcher
from newshub.models import NewsItem

logger = logging.getLogger(__name__)

REUTERS_URL = "https://www.reuters.com"
REUTERS_WIRE_URL = "https://www.reuters.com/news/archive/worldNews"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


class ReutersFetcher(BaseFetcher):
    """Fetch top news from Reuters by scraping the website."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.layer: str = config.get("layer", "breaking")
        self.sections: list[str] = config.get("sections", ["world", "business", "technology"])

    async def fetch(self) -> list[NewsItem]:
        items = await self._fetch_from_sections()
        if items:
            return items
        return await self._fetch_from_homepage()

    async def _fetch_from_sections(self) -> list[NewsItem]:
        items: list[NewsItem] = []
        try:
            async with httpx.AsyncClient(
                timeout=15, headers=HEADERS, follow_redirects=True
            ) as client:
                for section in self.sections:
                    url = f"{REUTERS_URL}/{section}/"
                    try:
                        resp = await client.get(url)
                        if resp.status_code != 200:
                            continue
                        items.extend(self._parse_section(resp.text, section))
                    except Exception:
                        logger.debug("Reuters section %s failed", section, exc_info=True)
        except Exception:
            logger.exception("Reuters section fetch failed")
        return items

    async def _fetch_from_homepage(self) -> list[NewsItem]:
        items: list[NewsItem] = []
        try:
            async with httpx.AsyncClient(
                timeout=15, headers=HEADERS, follow_redirects=True
            ) as client:
                resp = await client.get(REUTERS_URL)
                resp.raise_for_status()
            items = self._parse_section(resp.text, "homepage")
        except Exception:
            logger.exception("Reuters homepage fetch failed")
        return items

    def _parse_section(self, html: str, section: str) -> list[NewsItem]:
        items: list[NewsItem] = []

        # Reuters embeds structured data in __NEXT_DATA__ JSON
        match = re.search(
            r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>',
            html,
            re.DOTALL,
        )
        if match:
            items = self._parse_next_data(match.group(1), section)
            if items:
                return items

        # Fallback: parse article links from HTML
        soup = BeautifulSoup(html, "lxml")
        seen: set[str] = set()
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            if not re.match(r"^/[a-z]+/[a-z0-9-]+-\d{4}-\d{2}-\d{2}", href):
                continue
            full_url = f"{REUTERS_URL}{href}"
            if full_url in seen:
                continue
            seen.add(full_url)

            title_text = link.get_text(strip=True)
            if not title_text or len(title_text) < 10:
                continue

            items.append(
                NewsItem(
                    title=title_text,
                    url=full_url,
                    source="reuters",
                    source_name="Reuters",
                    layer=self.layer,
                    score=max(0.0, 100.0 - len(items) * 2),
                )
            )
            if len(items) >= 30:
                break
        return items

    def _parse_next_data(self, json_str: str, section: str) -> list[NewsItem]:
        items: list[NewsItem] = []
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return []

        articles = self._extract_articles(data)
        for i, article in enumerate(articles[:30]):
            title = article.get("title", "").strip()
            canonical = article.get("canonicalUrl", "")
            url = f"{REUTERS_URL}{canonical}" if canonical and not canonical.startswith("http") else canonical
            if not title or not url:
                continue

            pub_str = article.get("published_time", "") or article.get("date", "")
            pub_date = self._parse_datetime(pub_str)

            items.append(
                NewsItem(
                    title=title,
                    url=url,
                    source="reuters",
                    source_name="Reuters",
                    layer=self.layer,
                    published_at=pub_date,
                    score=max(0.0, 100.0 - i * 2),
                    summary=article.get("description", "")[:200],
                )
            )
        return items

    def _extract_articles(self, data: dict) -> list[dict]:
        """Recursively search for article-like objects in __NEXT_DATA__."""
        results: list[dict] = []
        self._walk(data, results, depth=0)
        return results

    def _walk(self, obj: Any, results: list[dict], depth: int) -> None:
        if depth > 8 or len(results) >= 50:
            return
        if isinstance(obj, dict):
            if "title" in obj and ("canonicalUrl" in obj or "url" in obj):
                results.append(obj)
            else:
                for v in obj.values():
                    self._walk(v, results, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                self._walk(item, results, depth + 1)

    @staticmethod
    def _parse_datetime(s: str) -> datetime | None:
        if not s:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None
