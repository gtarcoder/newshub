from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from newshub.fetchers.base import BaseFetcher
from newshub.models import NewsItem

logger = logging.getLogger(__name__)

ZHIHU_MOBILE_API = "https://api.zhihu.com/topstory/hot-lists/total?limit=50"
ZHIHU_WEB_API = (
    "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total"
    "?limit=50&desktop=true"
)
ZHIHU_QUESTION_URL = "https://www.zhihu.com/question/{qid}"

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)
DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


class ZhihuFetcher(BaseFetcher):
    """Fetch trending topics from Zhihu Hot List."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.layer: str = config.get("layer", "default")

    async def fetch(self) -> list[NewsItem]:
        # Strategy 1: Mobile API (no auth needed)
        items = await self._fetch_mobile_api()
        if items:
            return items

        # Strategy 2: Web API with optional cookie
        items = await self._fetch_web_api()
        if items:
            return items

        logger.warning(
            "All Zhihu fetch strategies failed. "
            "Consider setting a cookie in config.yaml under sources.zhihu.cookie"
        )
        return []

    async def _fetch_mobile_api(self) -> list[NewsItem]:
        headers = {"User-Agent": MOBILE_UA}
        try:
            async with httpx.AsyncClient(
                timeout=15, headers=headers, follow_redirects=True
            ) as client:
                resp = await client.get(ZHIHU_MOBILE_API)
                if resp.status_code in (401, 403):
                    logger.debug("Zhihu mobile API returned %d", resp.status_code)
                    return []
                resp.raise_for_status()
                return self._parse_api_response(resp.json())
        except Exception:
            logger.debug("Zhihu mobile API failed", exc_info=True)
            return []

    async def _fetch_web_api(self) -> list[NewsItem]:
        cookie_str = self.config.get("cookie", "")
        headers = {
            "User-Agent": DESKTOP_UA,
            "Referer": "https://www.zhihu.com/hot",
            "x-requested-with": "fetch",
        }
        cookies = self._parse_cookie_string(cookie_str) if cookie_str else None
        try:
            async with httpx.AsyncClient(
                timeout=15, headers=headers, cookies=cookies, follow_redirects=True
            ) as client:
                resp = await client.get(ZHIHU_WEB_API)
                if resp.status_code in (401, 403):
                    return []
                resp.raise_for_status()
                return self._parse_api_response(resp.json())
        except Exception:
            logger.debug("Zhihu web API failed", exc_info=True)
            return []

    def _parse_api_response(self, data: dict) -> list[NewsItem]:
        items: list[NewsItem] = []
        for entry in data.get("data", []):
            target = entry.get("target", {})
            title = target.get("title", "").strip()
            qid = target.get("id", "")
            excerpt = target.get("excerpt", "")
            heat_text = entry.get("detail_text", "0")
            answer_count = target.get("answer_count", 0)

            if not title:
                continue

            url = ZHIHU_QUESTION_URL.format(qid=qid)
            heat = self._parse_heat(heat_text, fallback_rank=len(items))

            summary = excerpt[:200] if excerpt else ""
            if answer_count:
                summary = f"{answer_count} 个回答 | {summary}" if summary else f"{answer_count} 个回答"

            items.append(
                NewsItem(
                    title=title,
                    url=url,
                    source="zhihu",
                    source_name="知乎热榜",
                    layer=self.layer,
                    score=heat,
                    summary=summary,
                )
            )
        return items

    @staticmethod
    def _parse_heat(text: str, fallback_rank: int = 0) -> float:
        cleaned = text.replace(" ", "").replace(",", "")
        multiplier = 1.0
        if "亿" in cleaned:
            multiplier = 1e8
        elif "万" in cleaned:
            multiplier = 1e4
        digits = ""
        for ch in cleaned:
            if ch.isdigit() or ch == ".":
                digits += ch
        try:
            val = float(digits) * multiplier
            return val if val > 0 else max(0.0, 1000.0 - fallback_rank * 10)
        except ValueError:
            return max(0.0, 1000.0 - fallback_rank * 10)

    @staticmethod
    def _parse_cookie_string(cookie_str: str) -> dict[str, str]:
        cookies: dict[str, str] = {}
        for pair in cookie_str.split(";"):
            pair = pair.strip()
            if "=" in pair:
                k, v = pair.split("=", 1)
                cookies[k.strip()] = v.strip()
        return cookies
