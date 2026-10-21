"""Google Trends qua pytrends (API không chính thức, hay bị giới hạn tốc độ).

Mỗi lô tối đa 5 từ khóa, trong đó 1 từ khóa neo ("du lịch") có mặt ở mọi lô. Chia giá trị của
từ khóa cho giá trị từ khóa neo trong cùng lô để các lô so sánh được với nhau. Nguồn này được
coi là tùy chọn: nếu bị chặn thì pipeline vẫn chạy tiếp với các tín hiệu còn lại.
"""
import logging
import time

from tourism.config import load_places
from tourism.db import transaction, upsert

log = logging.getLogger(__name__)
ANCHOR = "du lịch"
BATCH = 4


def fetch_batch(pytrends, keywords: list[str]) -> dict[str, list[tuple]]:
    pytrends.build_payload([ANCHOR, *keywords], timeframe="now 7-d", geo="VN")
    df = pytrends.interest_over_time()
    if df.empty:
        return {}
    out: dict[str, list[tuple]] = {}
    for kw in keywords:
        series = []
        for ts, row in df.iterrows():
            anchor = max(row[ANCHOR], 1)
            series.append((ts.to_pydatetime().replace(tzinfo=None), round(100 * row[kw] / anchor)))
        out[kw] = series
    return out


def run(dry_run: bool = False) -> int:
    from pytrends.request import TrendReq

    places = [p for p in load_places() if p.trends_keyword]
    by_kw = {p.trends_keyword: p.place_id for p in places}
    keywords = list(by_kw)
    pytrends = TrendReq(hl="vi-VN", tz=-420, timeout=(10, 30))
    rows: list[tuple] = []
    for i in range(0, len(keywords), BATCH):
        batch = keywords[i : i + BATCH]
        try:
            for kw, series in fetch_batch(pytrends, batch).items():
                rows.extend((by_kw[kw], ts, v) for ts, v in series)
        except Exception as exc:  # noqa: BLE001 - nguồn tùy chọn, lỗi thì bỏ qua lô này
            log.warning("Google Trends lỗi ở lô %s: %s", batch, exc)
        time.sleep(5)
    if dry_run:
        print(rows[:3])
        return len(rows)
    with transaction() as cur:
        return upsert(cur, "raw.trends_interest", ["place_id", "ts", "interest"], rows, ["place_id", "ts"])
