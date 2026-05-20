# MEMORY

本文件是仓库内记忆系统的入口与索引，所有重要记忆以文件持久化。

## A. 长期记忆（Long-term）
- 存放内容：稳定规则、长期偏好、跨任务可复用事实。
- 更新原则：只保留高价值、低时效噪音的信息。
- 记录格式（建议）：
  - 事实：
  - 来源：
  - 生效范围：
  - 最后更新：

## B. 每日/临时记录（Daily / Temporary）
- 存放内容：当天目标、过程笔记、临时结论、短期待办。
- 文件建议：`memory/daily/YYYY-MM-DD.md`
- 清理原则：过期即归档或删除，避免污染长期记忆。

## C. 当前约定
- 角色与工作方式主定义：`/AGENTS.md`
- 重要信息不得仅存在于聊天记录，必须同步到仓库文件。
- 项目级技能统一放置在：`.agents/ski11s/`。
- `ski11s` 命名为显式仓库约定，按需求保留。
- 技能目录按 `.agents/ski11s/<skill-id>/` 组织，最低要求 `skill.yaml` + `README.md`。
- 通过 GitHub Actions 工作流 `skills-registry-check.yml` 校验技能目录与元数据约束。

## D. 最近更新
- 财经简报改为每小时定时更新：`.github/workflows/finance-digest.yml`。
- 摘要生成脚本增加正文抓取与单条摘要/解读：`scripts/generate_finance_digest.py`。
- 输出文件改为带时间戳的 `reports/us-finance-digest-YYYYmmdd-HHMMSS.md`（每次生成新文件）。
- 接入 follow-news 数据源与技能目录：`.agents/ski11s/follow-news/`、`data/follow-news-rss.json`。
