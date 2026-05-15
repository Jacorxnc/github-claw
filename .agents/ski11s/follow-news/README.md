# Follow News

该技能用于接入 [tangwz/follow-news](https://github.com/tangwz/follow-news) 提供的新闻数据源，
便于在本仓库的新闻聚合任务中复用其 RSS 源配置。

## 数据来源

- 上游仓库：`tangwz/follow-news`
- RSS 源清单：`data/follow-news-rss.json`

## 使用说明

- 新闻摘要脚本会读取 `data/follow-news-rss.json` 作为额外 RSS 数据源。
- 需要更新来源时，请同步上游 `config/defaults/sources.json` 的 RSS 部分。
