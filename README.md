# NewsHub — 新闻热点聚合推送系统

抓取多层新闻源的热点内容，排序去重后按层推送 Top N 到微信 / 飞书。

## 信息分层

| 层 | 标签 | 用途 | 信息源 | 默认调度 |
|---|---|---|---|---|
| `breaking` | 快讯热点 | 发现热点 | 华尔街见闻、POLITICO、Reuters | 每天 8/12/18 点 |
| `deep` | 深度解读 | 解释热点 | Economist、FT、财新、Foreign Affairs | 每天 9 点 |
| `tech` | 科技前沿 | 筛科技热点 | MIT Tech Review、MIT News | 每天 8/18 点 |
| `ideas` | 思想精选 | 低频精选 | Aeon | 每周一 10 点 |
| `default` | 综合热点 | 综合信息 | 36氪、少数派、知乎、Hacker News | 每天 8/12/18 点 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 编辑配置

编辑 `config.yaml`，启用需要的信息源和推送通道。敏感信息通过环境变量注入：

```bash
export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
export SERVERCHAN_KEY="your-key"
export NEWSAPI_KEY="your-api-key"
```

### 3. 运行

```bash
# 运行单个层
python main.py --layer breaking --top 10

# 运行所有层
python main.py --all-layers

# 仅抓取指定源
python main.py --source wallstreetcn --top 5

# 综合模式（无分层，兼容旧用法）
python main.py --run-now

# 启动定时调度（每个层按各自 cron 独立运行）
python main.py
```

## CLI 参数

| 参数 | 说明 |
|---|---|
| `--layer`, `-l` | 运行指定层：`breaking`, `deep`, `tech`, `ideas`, `default` |
| `--all-layers` | 依次运行所有层 |
| `--run-now` | 立即执行一次（不分层） |
| `--source`, `-s` | 仅从指定源采集 |
| `--top`, `-n` | 覆盖 top_n 配置值 |
| `--config`, `-c` | 指定配置文件路径 |
| `--verbose`, `-v` | 输出详细日志 |

## 信息源

| 源 | 类型 | 默认层 | 需要配置 |
|---|---|---|---|
| RSS (36氪, 少数派) | RSS | default | feed URL |
| POLITICO | RSS | breaking | 无 |
| Economist | RSS | deep | 无 |
| FT World | RSS | deep | 无 |
| Foreign Affairs | RSS | deep | 无 |
| MIT Tech Review | RSS | tech | 无 |
| MIT News | RSS | tech | 无 |
| Aeon | RSS | ideas | 无 |
| 华尔街见闻 | API | breaking | 无 |
| Reuters | 网页抓取 | breaking | 无 |
| 财新 | API + 网页 | deep | 无 |
| 知乎热榜 | API | default | 无（可选 cookie） |
| Hacker News | API | default | 无 |
| NewsAPI | API | default | API Key |

## 推送通道

| 通道 | 说明 | 需要配置 |
|---|---|---|
| 微信 (Server酱) | 推送到微信 | [Server酱](https://sct.ftqq.com/) Key |
| 飞书机器人 | 飞书群 Webhook | Webhook URL |

## 配置示例

```yaml
layers:
  breaking:
    label: "快讯热点"
    top_n: 15
    schedule: "0 8,12,18 * * *"
  deep:
    label: "深度解读"
    top_n: 10
    schedule: "0 9 * * *"
  tech:
    label: "科技前沿"
    top_n: 10
    schedule: "0 8,18 * * *"
  ideas:
    label: "思想精选"
    top_n: 5
    schedule: "0 10 * * 1"    # 每周一
```

每个 RSS feed 可以通过 `layer` 字段指定所属层：

```yaml
sources:
  rss:
    enabled: true
    feeds:
      - name: "POLITICO"
        url: "https://rss.politico.com/politics.xml"
        layer: breaking
      - name: "MIT Tech Review"
        url: "https://www.technologyreview.com/feed/"
        layer: tech
```

## 扩展指南

### 添加信息源

1. 在 `newshub/fetchers/` 下创建新文件，继承 `BaseFetcher`
2. 实现 `async fetch() -> list[NewsItem]`，为每条设置 `layer` 字段
3. 在 `newshub/scheduler.py` 的 `FETCHER_MAP` 中注册
4. 在 `config.yaml` 中添加配置段（含 `layer` 字段）

### 添加推送通道

1. 在 `newshub/pushers/` 下创建新文件，继承 `BasePusher`
2. 实现 `async push(items, title) -> bool`
3. 在 `newshub/scheduler.py` 的 `PUSHER_MAP` 中注册

## 项目结构

```
newshub/
├── config.yaml
├── requirements.txt
├── main.py
└── newshub/
    ├── models.py
    ├── config.py
    ├── ranker.py
    ├── formatters.py
    ├── scheduler.py
    ├── fetchers/
    │   ├── base.py
    │   ├── rss.py          # RSS/Atom (多源复用)
    │   ├── newsapi.py
    │   ├── zhihu.py
    │   ├── hackernews.py
    │   ├── wallstreetcn.py  # 华尔街见闻
    │   ├── reuters.py       # Reuters 网页抓取
    │   └── caixin.py        # 财新
    └── pushers/
        ├── base.py
        ├── wechat.py
        └── feishu.py
```
