#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import html
import json
import pathlib
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "reports" / "us-finance-digest.md"
MAX_ITEMS_PER_SOURCE = 8
TIMEOUT_SECONDS = 20
USER_AGENT = "github-claw-finance-digest/1.0"

SOURCES = [
    {
        "name": "CNBC Markets",
        "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    },
    {
        "name": "CNBC Economy",
        "url": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    },
    {
        "name": "MarketWatch Top Stories",
        "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    },
    {
        "name": "Yahoo Finance",
        "url": "https://finance.yahoo.com/news/rssindex",
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
}


@dataclass
class Entry:
    source: str
    title: str
    link: str
    published: str


def fetch_feed(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="replace")


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


def to_markdown(grouped: dict[str, list[Entry]], errors: list[dict[str, str]]) -> str:
    now_utc = dt.datetime.now(dt.timezone.utc)
    lines = [
        "# 美股与全球财经半小时简报",
        "",
        f"- 更新时间（UTC）：{now_utc.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 数据源数量：{len(SOURCES)}",
        "- 说明：自动抓取财经网站公开 RSS/Atom 标题并按主题粗分类。",
        "",
    ]

    ordered_topics = ["美股市场", "美国经济", "全球政治经济", "其他重要财经动态"]
    for topic in ordered_topics:
        items = grouped.get(topic, [])
        lines.append(f"## {topic}")
        if not items:
            lines.append("- 暂无匹配新闻")
            lines.append("")
            continue
        for item in items[:20]:
            title = sanitize(item.title)
            source = sanitize(item.source)
            lines.append(f"- [{title}]({item.link})（来源：{source}）")
        lines.append("")

    lines.append("## 抓取状态")
    if not errors:
        lines.append("- 所有数据源抓取成功")
    else:
        lines.append(f"- 有 {len(errors)} 个数据源抓取失败：")
        for error in errors:
            lines.append(f"  - {sanitize(error['source'])}: {sanitize(error['error'])}")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(errors, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def sanitize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def main() -> None:
    all_entries: list[Entry] = []
    errors: list[dict[str, str]] = []

    for source in SOURCES:
        name = source["name"]
        url = source["url"]
        try:
            xml_text = fetch_feed(url)
            entries = parse_entries(name, xml_text)
            all_entries.extend(entries)
        except (urllib.error.URLError, TimeoutError, ET.ParseError, ValueError) as exc:
            errors.append({"source": name, "error": str(exc)})

    grouped: dict[str, list[Entry]] = {}
    for entry in all_entries:
        topic = classify_topic(entry.title)
        grouped.setdefault(topic, []).append(entry)

    markdown = to_markdown(grouped, errors)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(markdown + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
