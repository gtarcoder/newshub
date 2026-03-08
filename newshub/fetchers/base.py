from __future__ import annotations

import abc
from typing import Any

from newshub.models import NewsItem


class BaseFetcher(abc.ABC):
    """Abstract base class for all news source fetchers."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    @abc.abstractmethod
    async def fetch(self) -> list[NewsItem]:
        """Fetch news items from the source and return them."""
        ...
