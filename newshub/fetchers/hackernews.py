from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from newshub.fetchers.base import BaseFetcher
from newshub.models import NewsItem

logger = logging.getLogger(__name__)

HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
HN_THREAD_URL = "https://news.ycombinator.com/item?id={item_id}"

MAX_CONCURRENT = 10


class HackerNewsFetcher(BaseFetcher):
    """Fetch top stories from Hacker News."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.top_n: int = config.get("top_n", 30)
        self.layer: str = config.get("layer", "default")

    async def fetch(self) -> list[NewsItem]:
        items: list[NewsItem] = []
        for trust_env in (True, False):
            try:
                async with httpx.AsyncClient(
                    timeout=15, trust_env=trust_env
                ) as client:
                    resp = await client.get(HN_TOP_URL)
                    resp.raise_for_status()
                    story_ids: list[int] = resp.json()[: self.top_n]

                    sem = asyncio.Semaphore(MAX_CONCURRENT)
                    tasks = [self._fetch_item(client, sem, sid, self.layer) for sid in story_ids]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                for r in results:
                    if isinstance(r, NewsItem):
                        items.append(r)
                    elif isinstance(r, Exception):
                        logger.warning("Failed to fetch HN item: %s", r)
                return items
            except (httpx.ConnectError, httpx.ConnectTimeout):
                if trust_env:
                    logger.info(
                        "HN fetch failed via proxy, retrying with direct connection"
                    )
                    continue
                logger.exception("Failed to fetch Hacker News top stories")
        return items

    @staticmethod
    async def _fetch_item(
        client: httpx.AsyncClient, sem: asyncio.Semaphore, item_id: int, layer: str = "default"
    ) -> NewsItem:
        async with sem:
            url = HN_ITEM_URL.format(item_id=item_id)
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        title = data.get("title", "")
        link = data.get("url") or HN_THREAD_URL.format(item_id=item_id)
        score = float(data.get("score", 0))
        ts = data.get("time")
        pub_date = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None

        return NewsItem(
            title=title,
            url=link,
            source="hackernews",
            source_name="Hacker News",
            layer=layer,
            published_at=pub_date,
            score=score,
            summary=f"Points: {int(score)} | Comments: {data.get('descendants', 0)}",
        )
