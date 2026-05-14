#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import html
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "reports" / "us-finance-digest.md"
FOLLOW_NEWS_RSS_PATH = REPO_ROOT / "data" / "follow-news-rss.json"
MAX_ITEMS_PER_SOURCE = 8
MAX_ITEMS_PER_TOPIC = 20
SUMMARY_KEYWORD_LIMIT = 4
TIMEOUT_SECONDS = 20
USER_AGENT = "Mozilla/5.0 (compatible; github-claw-finance-digest/1.0)"
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_BASE = 2  # seconds

# CNBC updated their RSS to search.cnbc.com format (old /device/rss/ URLs deprecated 2023)
BASE_SOURCES = [
    {
        "name": "CNBC Markets",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    },
    {
        "name": "CNBC Economy",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    },
    {
        "name": "Reuters Business",
        "url": "https://feeds.reuters.com/reuters/businessNews",
    },
    {
        "name": "Reuters Markets",
        "url": "https://feeds.reuters.com/reuters/marketsNews",
    },
]

TOPIC_KEYWORDS = {
    "美股市场": ["dow", "nasdaq", "s&p", "wall street", "stocks", "equity", "market", "earnings", "ipo"],
    "美国经济": [
        "fed",
        "federal reserve",
        "inflation",
        "cpi",
        "jobs",
        "employment",
        "gdp",
        "recession",
        "consumer",
        "retail sales",
        "treasury",
    ],
    "全球政治经济": [
        "china",
        "europe",
        "russia",
        "ukraine",
        "tariff",
        "trade",
        "sanction",
        "opec",
        "oil",
        "middle east",
        "geopolit",
    ],
    "科技与AI动态": [
        "ai",
        "artificial intelligence",
        "llm",
        "model",
        "agent",
        "openai",
        "anthropic",
        "deepmind",
        "mistral",
        "nvidia",
        "chip",
        "semiconductor",
        "gpu",
        "robot",
        "automation",
        "startup",
        "software",
        "cloud",
        "data center",
        "open-source",
        "github",
        "开源",
        "人工智能",
        "大模型",
        "芯片",
        "算力",
        "机器人",
    ],
}

TOPIC_ORDER = ["美股市场", "美国经济", "全球政治经济", "科技与AI动态", "其他重要财经动态"]

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+\-]{1,}|[\u4e00-\u9fff]{2,}")

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "over",
    "says",
    "say",
    "that",
    "the",
    "this",
    "to",
    "with",
    "after",
    "ahead",
    "amid",
    "near",
    "new",
    "news",
    "report",
    "reports",
    "will",
    "us",
    "u",
    "up",
    "down",
    "more",
    "less",
    "than",
    "year",
    "years",
}


@dataclass
class Entry:
    source: str
    title: str
    link: str
    published: str


def load_follow_news_sources() -> list[dict[str, str]]:
    if not FOLLOW_NEWS_RSS_PATH.exists():
        return []
    try:
        payload = json.loads(FOLLOW_NEWS_RSS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Failed to load follow-news sources: {exc}", file=sys.stderr)
        return []

    items = payload.get("sources", []) if isinstance(payload, dict) else payload
    sources: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        url = str(item.get("url", "")).strip()
        if name and url:
            sources.append({"name": name, "url": url})
    return sources


def merge_sources(*source_lists: list[dict[str, str]]) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for source_list in source_lists:
        for source in source_list:
            url = source.get("url", "")
            if not url or url in seen_urls:
                continue
            merged.append(source)
            seen_urls.add(url)
    return merged


def load_sources() -> list[dict[str, str]]:
    return merge_sources(BASE_SOURCES, load_follow_news_sources())


def fetch_feed(url: str) -> str:
    last_exc: Exception | None = None
    for attempt in range(max(RETRY_ATTEMPTS, 1)):
        if attempt > 0:
            time.sleep(RETRY_BACKOFF_BASE ** attempt)
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc
    raise last_exc  # type: ignore[misc]


def parse_entries(source_name: str, xml_text: str) -> list[Entry]:
    root = ET.fromstring(xml_text)
    entries: list[Entry] = []

    channel_items = root.findall("./channel/item")
    if channel_items:
        for item in channel_items[:MAX_ITEMS_PER_SOURCE]:
            title = text_of(item, "title")
            link = text_of(item, "link")
            published = text_of(item, "pubDate") or text_of(item, "dc:date") or ""
            if title and link:
                entries.append(Entry(source=source_name, title=title, link=link, published=published))
        return entries

    atom_entries = root.findall("{http://www.w3.org/2005/Atom}entry")
    for item in atom_entries[:MAX_ITEMS_PER_SOURCE]:
        title = text_of(item, "{http://www.w3.org/2005/Atom}title")
        link_el = item.find("{http://www.w3.org/2005/Atom}link")
        link = link_el.attrib.get("href", "") if link_el is not None else ""
        published = text_of(item, "{http://www.w3.org/2005/Atom}updated")
        if title and link:
            entries.append(Entry(source=source_name, title=title, link=link, published=published))
    return entries


def text_of(parent: ET.Element, tag: str) -> str:
    namespaces = {"dc": "http://purl.org/dc/elements/1.1/"}
    try:
        node = parent.find(tag, namespaces)
    except SyntaxError:
        node = None
    return html.unescape(node.text.strip()) if node is not None and node.text else ""


def classify_topic(title: str) -> str:
    text = title.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return topic
    return "其他重要财经动态"


def extract_keywords(titles: list[str], limit: int = SUMMARY_KEYWORD_LIMIT) -> list[str]:
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    for title in titles:
        for token in TOKEN_RE.findall(title):
            normalized = token.lower()
            if normalized in STOPWORDS or normalized.isdigit():
                continue
            counts[normalized] += 1
            display.setdefault(normalized, token)
    sorted_tokens = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [display[token] for token, _ in sorted_tokens[:limit]]


def interpret_topic(topic: str, keyword_text: str) -> str:
    templates = {
        "美股市场": "交易与公司消息集中在{keywords}，显示市场在风险偏好与板块轮动上仍受这些变量牵引。",
        "美国经济": "宏观数据与政策相关报道聚焦{keywords}，表明通胀与货币政策预期仍是核心定价因素。",
        "全球政治经济": "地缘与大宗商品事件围绕{keywords}，提示外部不确定性可能继续影响全球资产情绪。",
        "科技与AI动态": "科技与AI相关消息聚焦{keywords}，显示新技术落地与产业竞争仍在加速。",
    }
    template = templates.get(topic, "多条报道涉及{keywords}，显示该领域仍有新的催化与风险点值得关注。")
    return template.format(keywords=keyword_text)


def summarize_topic(topic: str, items: list[Entry]) -> tuple[str, str]:
    if not items:
        return "暂无匹配新闻", "暂无解读"
    keywords = extract_keywords([item.title for item in items])
    keyword_text = "、".join(keywords) if keywords else "核心事件"
    summary = f"本期共{len(items)}条，重点围绕{keyword_text}。"
    interpretation = interpret_topic(topic, keyword_text)
    return sanitize(summary), sanitize(interpretation)


def build_overview(grouped: dict[str, list[Entry]]) -> tuple[str, str]:
    total_items = sum(len(items) for items in grouped.values())
    if total_items == 0:
        return "本期暂无可汇总的有效新闻。", "请稍后再试或关注下一轮更新。"

    topic_counts = [(topic, len(items)) for topic, items in grouped.items() if items]
    topic_counts.sort(key=lambda item: (-item[1], item[0]))
    top_topics = "、".join(f"{topic}({count}条)" for topic, count in topic_counts[:3])
    all_titles = [entry.title for items in grouped.values() for entry in items]
    keywords = extract_keywords(all_titles)
    keyword_text = "、".join(keywords) if keywords else "市场与产业热点"

    summary = f"共汇总{total_items}条新闻，主要集中在{top_topics}，高频关键词包括{keyword_text}。"
    interpretation = "整体信息显示宏观与行业变量交织，短期情绪仍可能随关键事件快速波动。"
    return sanitize(summary), sanitize(interpretation)


def to_markdown(grouped: dict[str, list[Entry]], source_count: int) -> str:
    now_utc = dt.datetime.now(dt.timezone.utc)
    total_items = sum(len(items) for items in grouped.values())
    overview_summary, overview_interpretation = build_overview(grouped)
    lines = [
        "# 美股与全球财经半小时简报",
        "",
        f"- 更新时间（UTC）：{now_utc.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 数据源数量：{source_count}",
        f"- 收录条目：{total_items}",
        "- 说明：自动抓取财经与科技网站公开 RSS/Atom 标题，并按主题进行汇总与解读。",
        "",
        "## 总览",
        f"- 汇总：{overview_summary}",
        f"- 解读：{overview_interpretation}",
        "",
    ]

    for topic in TOPIC_ORDER:
        items = grouped.get(topic, [])
        lines.append(f"## {topic}")
        summary, interpretation = summarize_topic(topic, items)
        lines.append(f"- 汇总：{summary}")
        lines.append(f"- 解读：{interpretation}")
        if not items:
            lines.append("")
            continue
        lines.append("")
        lines.append("### 相关报道")
        for item in items[:MAX_ITEMS_PER_TOPIC]:
            title = sanitize(item.title)
            source = sanitize(item.source)
            lines.append(f"- [{title}]({item.link})（来源：{source}）")
        lines.append("")

    return "\n".join(lines)


def sanitize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def log_errors(errors: list[dict[str, str]]) -> None:
    if not errors:
        return
    print(f"{len(errors)} sources failed to fetch:", file=sys.stderr)
    for error in errors:
        source = sanitize(error.get("source", ""))
        message = sanitize(error.get("error", ""))
        print(f"- {source}: {message}", file=sys.stderr)


def main() -> None:
    all_entries: list[Entry] = []
    errors: list[dict[str, str]] = []

    sources = load_sources()
    for source in sources:
        name = source["name"]
        url = source["url"]
        try:
            xml_text = fetch_feed(url)
            entries = parse_entries(name, xml_text)
            all_entries.extend(entries)
        except (urllib.error.URLError, TimeoutError, OSError, ET.ParseError, ValueError) as exc:
            errors.append({"source": name, "error": str(exc)})

    grouped: dict[str, list[Entry]] = {}
    for entry in all_entries:
        topic = classify_topic(entry.title)
        grouped.setdefault(topic, []).append(entry)

    markdown = to_markdown(grouped, source_count=len(sources))
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(markdown + "\n", encoding="utf-8")
    log_errors(errors)


if __name__ == "__main__":
    main()
