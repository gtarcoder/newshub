from __future__ import annotations

import logging
from typing import Any

import httpx

from newshub.formatters import to_feishu_card
from newshub.pushers.base import BasePusher
from newshub.ranker import GroupedItems

logger = logging.getLogger(__name__)


class FeishuPusher(BasePusher):
    """Push news via Feishu (Lark) custom bot webhook."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.webhook_url: str = config.get("webhook_url", "")

    async def push(self, grouped: GroupedItems, title: str | None = None) -> bool:
        if not self.webhook_url or self.webhook_url.startswith("${"):
            logger.warning("Feishu webhook URL not configured, skipping")
            return False

        payload = to_feishu_card(grouped, title=title)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(self.webhook_url, json=payload)
                resp.raise_for_status()
                result = resp.json()

            if result.get("code") == 0 or result.get("StatusCode") == 0:
                logger.info("Feishu push succeeded")
                return True
            logger.error("Feishu push failed: %s", result)
            return False
        except Exception:
            logger.exception("Feishu push error")
            return False
