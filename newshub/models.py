from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

LAYER_LABELS: dict[str, str] = {
    "breaking": "快讯热点",
    "deep": "深度解读",
    "tech": "科技前沿",
    "ideas": "思想精选",
    "default": "综合热点",
}


@dataclass
class NewsItem:
    title: str
    url: str
    source: str  # e.g. "rss", "newsapi", "zhihu", "hackernews", "wallstreetcn"
    source_name: str  # e.g. "36氪", "知乎热榜", "POLITICO"
    layer: str = "default"  # "breaking", "deep", "tech", "ideas", "default"
    published_at: datetime | None = None
    score: float = 0.0
    summary: str = ""

    def __hash__(self) -> int:
        return hash(self.url)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NewsItem):
            return NotImplemented
        return self.url == other.url
