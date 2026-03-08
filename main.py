#!/usr/bin/env python3
"""NewsHub — News hotspot aggregation & push system."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from newshub.config import load_config
from newshub.scheduler import run_all_layers, run_pipeline, start_scheduler

ALL_SOURCES = [
    "rss", "newsapi", "zhihu", "hackernews",
    "wallstreetcn", "reuters", "caixin",
]
ALL_LAYERS = ["breaking", "deep", "tech", "ideas", "default"]


def main() -> None:
    parser = argparse.ArgumentParser(description="NewsHub: 新闻热点聚合推送系统")
    parser.add_argument(
        "--config", "-c", default=None, help="配置文件路径 (默认 config.yaml)"
    )
    parser.add_argument(
        "--run-now", action="store_true", help="立即执行一次，不启动定时调度"
    )
    parser.add_argument(
        "--source", "-s", default=None, choices=ALL_SOURCES,
        help="仅从指定新闻源采集",
    )
    parser.add_argument(
        "--layer", "-l", default=None, choices=ALL_LAYERS,
        help="仅运行指定层 (breaking/deep/tech/ideas/default)",
    )
    parser.add_argument(
        "--all-layers", action="store_true",
        help="依次运行所有层",
    )
    parser.add_argument(
        "--top", "-n", type=int, default=None, help="覆盖 top_n 配置值"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="输出详细日志"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    config = load_config(args.config)

    if args.all_layers:
        asyncio.run(run_all_layers(config, top_n_override=args.top))
    elif args.run_now or args.source or args.layer:
        asyncio.run(
            run_pipeline(
                config,
                only_source=args.source,
                only_layer=args.layer,
                top_n_override=args.top,
            )
        )
    else:
        start_scheduler(config)


if __name__ == "__main__":
    main()
