from __future__ import annotations

import asyncio
import logging
from typing import Any

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from newshub.config import load_config
from newshub.fetchers.base import BaseFetcher
from newshub.fetchers.caixin import CaixinFetcher
from newshub.fetchers.hackernews import HackerNewsFetcher
from newshub.fetchers.newsapi import NewsAPIFetcher
from newshub.fetchers.reuters import ReutersFetcher
from newshub.fetchers.rss import RSSFetcher
from newshub.fetchers.wallstreetcn import WallStreetCNFetcher
from newshub.fetchers.zhihu import ZhihuFetcher
from newshub.formatters import to_plain_text
from newshub.models import LAYER_LABELS, NewsItem
from newshub.pushers.base import BasePusher
from newshub.pushers.feishu import FeishuPusher
from newshub.pushers.wechat import WeChatPusher
from newshub.ranker import GroupedItems, rank_by_source

logger = logging.getLogger(__name__)

FETCHER_MAP: dict[str, type[BaseFetcher]] = {
    "rss": RSSFetcher,
    "newsapi": NewsAPIFetcher,
    "zhihu": ZhihuFetcher,
    "hackernews": HackerNewsFetcher,
    "wallstreetcn": WallStreetCNFetcher,
    "reuters": ReutersFetcher,
    "caixin": CaixinFetcher,
}

PUSHER_MAP: dict[str, type[BasePusher]] = {
    "wechat": WeChatPusher,
    "feishu": FeishuPusher,
}


def _build_fetchers(
    config: dict[str, Any],
    only_source: str | None = None,
    only_layer: str | None = None,
) -> list[BaseFetcher]:
    """Build fetcher instances, optionally filtered by source name or layer."""
    fetchers: list[BaseFetcher] = []
    sources_cfg = config.get("sources", {})

    for name, cls in FETCHER_MAP.items():
        if only_source and name != only_source:
            continue
        src_cfg = sources_cfg.get(name, {})
        if not (src_cfg.get("enabled", False) or only_source == name):
            continue

        if name == "rss" and only_layer:
            # For RSS, filter individual feeds by layer
            filtered_feeds = [
                f for f in src_cfg.get("feeds", [])
                if f.get("layer", src_cfg.get("layer", "default")) == only_layer
            ]
            if not filtered_feeds:
                continue
            filtered_cfg = {**src_cfg, "feeds": filtered_feeds, "layer": only_layer}
            fetchers.append(cls(filtered_cfg))
        elif only_layer:
            src_layer = src_cfg.get("layer", "default")
            if src_layer != only_layer:
                continue
            fetchers.append(cls(src_cfg))
        else:
            fetchers.append(cls(src_cfg))

    return fetchers


def _build_pushers(config: dict[str, Any]) -> list[BasePusher]:
    pushers: list[BasePusher] = []
    push_cfg = config.get("push", {})
    for name, cls in PUSHER_MAP.items():
        ch_cfg = push_cfg.get(name, {})
        if ch_cfg.get("enabled", False):
            pushers.append(cls(ch_cfg))
    return pushers


def _get_layer_config(config: dict[str, Any], layer: str) -> dict[str, Any]:
    return config.get("layers", {}).get(layer, {})


async def run_pipeline(
    config: dict[str, Any],
    only_source: str | None = None,
    only_layer: str | None = None,
    top_n_override: int | None = None,
) -> GroupedItems:
    """Execute the full fetch -> rank (per source) -> push pipeline."""
    fetchers = _build_fetchers(config, only_source=only_source, only_layer=only_layer)
    if not fetchers:
        logger.warning("No fetchers enabled (source=%s, layer=%s)", only_source, only_layer)
        return GroupedItems()

    tasks = [f.fetch() for f in fetchers]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_items: list[NewsItem] = []
    for r in results:
        if isinstance(r, list):
            all_items.extend(r)
        elif isinstance(r, Exception):
            logger.error("Fetcher error: %s", r)

    layer_cfg = _get_layer_config(config, only_layer or "default")
    ranking_cfg = config.get("ranking", {})
    top_n = top_n_override or layer_cfg.get("top_n", ranking_cfg.get("top_n", 10))
    dedup = ranking_cfg.get("dedup", True)
    grouped = rank_by_source(all_items, top_n=top_n, dedup=dedup)

    total_ranked = sum(len(v) for v in grouped.values())
    layer_label = layer_cfg.get("label", LAYER_LABELS.get(only_layer or "default", "新闻热点"))
    title = layer_label
    logger.info(
        "[%s] Fetched %d items → %d sources, top %d each",
        layer_label, len(all_items), len(grouped), top_n,
    )

    pushers = _build_pushers(config)
    if pushers:
        push_tasks = [p.push(grouped, title=title) for p in pushers]
        await asyncio.gather(*push_tasks, return_exceptions=True)
    else:
        print(to_plain_text(grouped, title=title))

    return grouped


async def run_all_layers(config: dict[str, Any], top_n_override: int | None = None) -> None:
    """Run the pipeline for every configured layer sequentially."""
    layers_cfg = config.get("layers", {})
    if not layers_cfg:
        await run_pipeline(config, top_n_override=top_n_override)
        return
    for layer_name in layers_cfg:
        await run_pipeline(config, only_layer=layer_name, top_n_override=top_n_override)


def _sync_layer_job(config: dict[str, Any], layer: str) -> None:
    asyncio.run(run_pipeline(config, only_layer=layer))


def start_scheduler(config: dict[str, Any]) -> None:
    """Start the blocking APScheduler with per-layer cron schedules."""
    tz = config.get("schedule", {}).get("timezone", "Asia/Shanghai")
    layers_cfg = config.get("layers", {})

    scheduler = BlockingScheduler(timezone=tz)

    if not layers_cfg:
        cron_expr = config.get("schedule", {}).get("cron", "0 8 * * *")
        trigger = _parse_cron(cron_expr, tz)
        scheduler.add_job(
            _sync_layer_job, trigger, args=[config, "default"], id="default"
        )
        logger.info("Scheduler: default — cron %s", cron_expr)
    else:
        for layer_name, layer_cfg in layers_cfg.items():
            cron_expr = layer_cfg.get("schedule", "0 8 * * *")
            trigger = _parse_cron(cron_expr, tz)
            scheduler.add_job(
                _sync_layer_job,
                trigger,
                args=[config, layer_name],
                id=f"layer_{layer_name}",
            )
            logger.info(
                "Scheduler: %s (%s) — cron %s",
                layer_name,
                layer_cfg.get("label", layer_name),
                cron_expr,
            )

    logger.info("Scheduler started (timezone: %s)", tz)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


def _parse_cron(cron_expr: str, tz: str) -> CronTrigger:
    parts = cron_expr.split()
    return CronTrigger(
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        day_of_week=parts[4],
        timezone=tz,
    )
