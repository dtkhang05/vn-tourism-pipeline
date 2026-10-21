import html
import logging
import re
from calendar import timegm
from datetime import UTC, datetime

import feedparser

from tourism.config import load_news_feeds
from tourism.db import transaction, upsert
from tourism.http import session

log = logging.getLogger(__name__)
TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str | None) -> str:
    return " ".join(html.unescape(TAG_RE.sub(" ", text or "")).split())


def fetch_feed(source: str, url: str) -> list[tuple]:
    resp = session().get(url, timeout=30)
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)
    rows = []
    for e in parsed.entries:
        link = e.get("link")
        if not link:
            continue
        published = e.get("published_parsed") or e.get("updated_parsed")
        published_at = datetime.fromtimestamp(timegm(published), tz=UTC) if published else None
        rows.append((link, source, _clean(e.get("title")), _clean(e.get("summary")), published_at))
    return rows


def run(dry_run: bool = False) -> int:
    rows: list[tuple] = []
    for feed in load_news_feeds():
        try:
            fetched = fetch_feed(feed["source"], feed["url"])
            log.info("%s: %d bài", feed["source"], len(fetched))
            rows.extend(fetched)
        except Exception as exc:  # noqa: BLE001 - một nguồn lỗi không làm hỏng cả lô
            log.warning("Bỏ qua %s: %s", feed["source"], exc)
    if dry_run:
        for r in rows[:5]:
            print(r[1], "|", r[2])
        return len(rows)
    with transaction() as cur:
        return upsert(
            cur,
            "raw.news_articles",
            ["url", "source", "title", "summary", "published_at"],
            rows,
            conflict=["url"],
        )
