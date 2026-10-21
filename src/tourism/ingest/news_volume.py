"""Số bài báo nhắc từng điểm, theo cửa sổ 7 ngày, từ Google News RSS (tìm kiếm có lọc ngày).

Khác với RSS của từng báo (chỉ giữ vài ngày gần nhất), nguồn này có lịch sử ngay lần chạy đầu nên có thể so tuần này
với các tuần trước mà không phải chờ tích lũy. Mỗi truy vấn trả tối đa ~100 bài; cửa sổ 7 ngày của các điểm lớn
nhất vẫn dưới mức đó nên số đếm không bị chặn trần.
"""
import logging
import re
import time
from datetime import date, timedelta
from email.utils import parsedate_to_datetime

from tourism.config import load_places
from tourism.db import transaction, upsert
from tourism.http import session

log = logging.getLogger(__name__)
URL = "https://news.google.com/rss/search"
PUB = re.compile(r"<pubDate>(.*?)</pubDate>")
WINDOWS_BACKFILL = 8  # 8 tuần: đủ cho "tháng" (4 tuần gần nhất so với 4 tuần trước đó)


def count_articles(http, name: str, start: date) -> int:
    end = start + timedelta(days=7)
    q = f'"{name}" du lịch after:{start.isoformat()} before:{end.isoformat()}'
    for attempt in range(4):
        r = http.get(URL, params={"q": q, "hl": "vi", "gl": "VN", "ceid": "VN:vi"}, timeout=30)
        if r.status_code == 429:
            time.sleep(5 * (attempt + 1))
            continue
        r.raise_for_status()
        days = [parsedate_to_datetime(x).date() for x in PUB.findall(r.text)]
        return sum(start <= d < end for d in days)  # biên "before" của Google gồm cả ngày cuối, nên đếm lại cho chắc
    raise RuntimeError("Google News giới hạn tốc độ quá lâu")


def run(dry_run: bool = False, days: int | None = None) -> int:
    """days = số tuần cần lấy lại (mặc định 2 tuần trọn gần nhất; truyền 56 để backfill 8 tuần)."""
    windows = WINDOWS_BACKFILL if days and days > 14 else 2
    # Cửa sổ neo theo tuần lịch (thứ Hai) và chỉ lấy tuần đã trọn, để mọi lần chạy cùng một pha, không phụ thuộc ngày chạy.
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    http = session()
    rows: list[tuple] = []
    for p in load_places():
        for k in range(windows):
            start = this_monday - timedelta(days=7 * (k + 1))
            try:
                rows.append((p.place_id, start, count_articles(http, p.name, start)))
            except Exception as exc:  # noqa: BLE001
                log.warning("Bỏ qua %s tuần %s: %s", p.place_id, start, exc)
            time.sleep(0.6)
    if dry_run:
        print(rows[:3])
        return len(rows)
    with transaction() as cur:
        return upsert(cur, "raw.news_volume", ["place_id", "window_start", "articles"], rows, ["place_id", "window_start"])
