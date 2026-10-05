"""Google News RSS ingestion. Reuses the query pattern from the reference
repo (news.google.com/rss/search) - that part worked fine there; what's
different is this just stores headlines as evidence rows (news_items),
it does NOT hand them to an LLM to "extract risks".
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime

import feedparser

RSS_URL = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"


@dataclass
class NewsRow:
    published_at: datetime
    title: str
    source: str | None
    url: str
    snippet: str | None


def _dedupe_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def fetch_company_news(company_name: str, max_items: int = 30) -> list[NewsRow]:
    query = company_name.replace(" ", "+")
    feed = feedparser.parse(RSS_URL.format(query=query))

    seen: set[str] = set()
    out: list[NewsRow] = []
    for entry in feed.entries[:max_items]:
        url = entry.get("link", "")
        if not url:
            continue
        key = _dedupe_key(url)
        if key in seen:
            continue
        seen.add(key)

        published = entry.get("published")
        try:
            published_at = parsedate_to_datetime(published) if published else datetime.utcnow()
        except (TypeError, ValueError):
            published_at = datetime.utcnow()

        source = None
        if "source" in entry and isinstance(entry["source"], dict):
            source = entry["source"].get("title")

        out.append(
            NewsRow(
                published_at=published_at,
                title=entry.get("title", ""),
                source=source,
                url=url,
                snippet=entry.get("summary"),
            )
        )
    return out
