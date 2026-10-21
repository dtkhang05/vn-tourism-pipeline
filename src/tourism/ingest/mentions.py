"""Bước biến đổi bằng Python: trích địa danh từ bài báo chưa xử lý và ghi raw.news_place_mentions."""
import logging

from tourism.config import load_places
from tourism.db import transaction, upsert
from tourism.places import PlaceMatcher

log = logging.getLogger(__name__)


def run(dry_run: bool = False) -> int:
    matcher = PlaceMatcher(load_places())
    with transaction() as cur:
        cur.execute("SELECT url, title, summary FROM raw.news_articles WHERE mentions_extracted_at IS NULL")
        articles = cur.fetchall()
        rows = [
            (url, m.place_id, m.in_title)
            for url, title, summary in articles
            for m in matcher.find(title, summary or "")
        ]
        log.info("%d bài mới, %d lượt nhắc địa danh", len(articles), len(rows))
        if dry_run:
            return len(rows)
        written = upsert(cur, "raw.news_place_mentions", ["article_url", "place_id", "in_title"], rows, ["article_url", "place_id"])
        cur.execute(
            "UPDATE raw.news_articles SET mentions_extracted_at = now() WHERE mentions_extracted_at IS NULL"
        )
        return written
