from __future__ import annotations

from collections import OrderedDict
from difflib import SequenceMatcher

from newshub.models import NewsItem

SIMILARITY_THRESHOLD = 0.65

GroupedItems = OrderedDict[str, list[NewsItem]]


def _deduplicate(items: list[NewsItem]) -> list[NewsItem]:
    """Remove duplicates based on URL identity and title similarity."""
    seen_urls: set[str] = set()
    kept: list[NewsItem] = []
    for item in items:
        if item.url in seen_urls:
            continue
        is_dup = False
        for existing in kept:
            ratio = SequenceMatcher(None, item.title, existing.title).ratio()
            if ratio >= SIMILARITY_THRESHOLD:
                if item.score > existing.score:
                    kept.remove(existing)
                    seen_urls.discard(existing.url)
                else:
                    is_dup = True
                break
        if not is_dup:
            seen_urls.add(item.url)
            kept.append(item)
    return kept


def rank_by_source(
    items: list[NewsItem], top_n: int = 10, dedup: bool = True
) -> GroupedItems:
    """Group items by source_name, sort within each group, take top N per source."""
    if dedup:
        items = _deduplicate(items)

    groups: dict[str, list[NewsItem]] = {}
    for item in items:
        groups.setdefault(item.source_name, []).append(item)

    result: GroupedItems = OrderedDict()
    for name in sorted(groups, key=lambda n: max(it.score for it in groups[n]), reverse=True):
        group = groups[name]
        group.sort(key=lambda it: it.score, reverse=True)
        result[name] = group[:top_n]

    return result
