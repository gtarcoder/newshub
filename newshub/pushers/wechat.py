from __future__ import annotations

import logging
from typing import Any

import httpx

from newshub.formatters import to_markdown
from newshub.pushers.base import BasePusher
from newshub.ranker import GroupedItems

logger = logging.getLogger(__name__)

SERVERCHAN_URL = "https://sctapi.ftqq.com/{key}.send"


class WeChatPusher(BasePusher):
    """Push news via Server酱 (ServerChan) to WeChat."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.key: str = config.get("key", "")

    async def push(self, grouped: GroupedItems, title: str | None = None) -> bool:
        if not self.key or self.key.startswith("${"):
            logger.warning("ServerChan key not configured, skipping WeChat push")
            return False

        title = title or "新闻热点"
        body = to_markdown(grouped, title=title)

        url = SERVERCHAN_URL.format(key=self.key)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, data={"title": title, "desp": body})
                resp.raise_for_status()
                result = resp.json()

            if result.get("code") == 0:
                logger.info("WeChat push succeeded")
                return True
            logger.error("WeChat push failed: %s", result)
            return False
        except Exception:
            logger.exception("WeChat push error")
            return False
