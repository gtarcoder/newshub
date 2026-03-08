from __future__ import annotations

from datetime import datetime, timezone

from newshub.models import NewsItem
from newshub.ranker import GroupedItems


def to_markdown(grouped: GroupedItems, title: str | None = None) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    heading = title or "新闻热点"
    lines = [f"# {heading}", f"*{now}*", ""]

    for source_name, items in grouped.items():
        lines.append(f"## {source_name}")
        lines.append("")
        for i, item in enumerate(items, 1):
            lines.append(f"**{i}. [{item.title}]({item.url})**")
            if item.summary:
                lines.append(f"   {item.summary}")
            lines.append("")

    return "\n".join(lines)


def to_plain_text(grouped: GroupedItems, title: str | None = None) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    heading = title or "新闻热点"
    lines = [heading, now, "=" * 50, ""]

    for source_name, items in grouped.items():
        lines.append(f"--- {source_name} (Top {len(items)}) ---")
        lines.append("")
        for i, item in enumerate(items, 1):
            lines.append(f"  {i}. {item.title}")
            lines.append(f"     {item.url}")
            if item.summary:
                lines.append(f"     {item.summary}")
            lines.append("")

    return "\n".join(lines)


def to_feishu_card(grouped: GroupedItems, title: str | None = None) -> dict:
    """Build a Feishu interactive card message payload."""
    heading = title or "新闻热点"
    elements: list[dict] = []

    for source_name, items in grouped.items():
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**{source_name}**"},
        })
        for i, item in enumerate(items, 1):
            text = f"{i}. [{item.title}]({item.url})"
            if item.summary:
                text += f"\n{item.summary}"
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": text}})
        elements.append({"tag": "hr"})

    if elements and elements[-1].get("tag") == "hr":
        elements.pop()

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": heading},
                "template": "blue",
            },
            "elements": elements,
        },
    }
