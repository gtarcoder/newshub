from __future__ import annotations

import abc
from typing import Any

from newshub.ranker import GroupedItems


class BasePusher(abc.ABC):
    """Abstract base class for push notification channels."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    @abc.abstractmethod
    async def push(self, grouped: GroupedItems, title: str | None = None) -> bool:
        """Push the grouped news items. Returns True on success."""
        ...
