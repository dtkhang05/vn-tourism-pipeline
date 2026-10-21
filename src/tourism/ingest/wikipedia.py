"""Lượt xem Wikipedia theo ngày, theo ngôn ngữ.

vi = người Việt tra cứu; en, ko, zh, ja = các thị trường khách quốc tế lớn. Tên bài ở ngôn ngữ khác được lấy tự động
từ liên kết ngôn ngữ của bài tiếng Việt (không cần khai báo tay), rồi lưu vào raw.place_wiki_titles.
Một điểm có thể có nhiều bài (`extra_wiki_titles`) khi bài bị đổi tên hoặc tách trang; lượt xem các bài được cộng theo ngày.
"""
import logging
import time
from collections import defaultdict
from datetime import date, timedelta
from urllib.parse import quote

from tourism.config import load_places
from tourism.db import transaction, upsert
from tourism.http import session

log = logging.getLogger(__name__)
API = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{lang}.wikipedia/all-access/user/{title}/daily/{start}/{end}"
VI_API = "https://vi.wikipedia.org/w/api.php"
FOREIGN_LANGS = ("en", "ko", "zh", "ja")
MAX_FAILED_SHARE = 0.02  # quá tỉ lệ bài lỗi này thì cả lần thu thập bị coi là lỗi
RETRY_ROUNDS = 3  # số vòng gọi lại các bài lỗi sau khi chạy hết danh sách
RETRY_PAUSE = 90  # giây nghỉ trước mỗi vòng gọi lại


def fetch_pageviews(lang: str, title: str, start: date, end: date) -> list[tuple[date, int]]:
    url = API.format(lang=lang, title=quote(title.replace(" ", "_"), safe=""), start=start.strftime("%Y%m%d"), end=end.strftime("%Y%m%d"))
    resp = session().get(url, timeout=30)
    if resp.status_code == 404:  # bài chưa có lượt xem trong khoảng này
        return []
    resp.raise_for_status()
    return [(date(int(i["timestamp"][:4]), int(i["timestamp"][4:6]), int(i["timestamp"][6:8])), i["views"]) for i in resp.json()["items"]]


def resolve_titles(vi_titles: list[tuple[str, str]]) -> set[tuple[str, str, str]]:
    """(place_id, lang, title) cho các ngôn ngữ nước ngoài, theo liên kết ngôn ngữ của bài tiếng Việt. Đầu vào: (place_id, tên bài vi)."""
    http = session()
    out: set[tuple[str, str, str]] = set()
    for lang in FOREIGN_LANGS:
        for i in range(0, len(vi_titles), 40):
            chunk = vi_titles[i : i + 40]
            titles = [t.replace("_", " ") for _, t in chunk]
            r = http.get(VI_API, params={"action": "query", "titles": "|".join(titles), "redirects": 1, "prop": "langlinks", "lllang": lang,
                                          "lllimit": "max", "format": "json", "formatversion": 2}, timeout=30)
            r.raise_for_status()
            q = r.json()["query"]
            norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
            red = {x["from"]: x["to"] for x in q.get("redirects", [])}
            pages = {pg["title"]: pg for pg in q["pages"]}
            for (pid, _), t in zip(chunk, titles, strict=True):
                links = pages.get(red.get(norm.get(t, t), norm.get(t, t)), {}).get("langlinks", [])
                if links:
                    out.add((pid, lang, links[0]["title"]))
            time.sleep(0.3)
    return out


def run(dry_run: bool = False, days: int = 14) -> int:
    end = date.today() - timedelta(days=1)  # dữ liệu ngày hôm nay chưa đầy đủ
    start = end - timedelta(days=days - 1)
    places = [p for p in load_places() if p.wiki_title]
    vi_titles = [(p.place_id, t) for p in places for t in (p.wiki_title, *p.extra_wiki_titles)]

    found = resolve_titles(vi_titles)  # chỉ ~8 request nên tra lại mỗi lần chạy, bài mới thêm vào cấu hình được nhận ngay
    targets = {(pid, "vi", t) for pid, t in vi_titles} | found
    if not dry_run:
        with transaction() as cur:
            upsert(cur, "raw.place_wiki_titles", ["place_id", "lang", "title"], sorted(targets), ["place_id", "lang", "title"])

    views: dict[tuple[str, str, date], int] = defaultdict(int)  # cộng lượt xem của các bài cùng điểm, cùng ngôn ngữ
    pending = sorted(targets)
    for attempt in range(RETRY_ROUNDS + 1):
        failed: list[tuple[str, str, str]] = []
        for pid, lang, title in pending:
            try:
                for d, v in fetch_pageviews(lang, title, start, end):
                    views[(pid, lang, d)] += v
            except Exception as exc:  # noqa: BLE001 - một bài lỗi không làm hỏng cả lô
                log.warning("Bỏ qua %s/%s/%s: %s", pid, lang, title, exc)
                failed.append((pid, lang, title))
            time.sleep(0.25)  # lịch sự với API công cộng; nhanh hơn thì bị giới hạn tần suất (429) khi có hơn ~60 điểm
        if not failed or attempt == RETRY_ROUNDS:
            break
        log.info("%d bài lỗi, nghỉ %ds rồi thử lại (vòng %d/%d)", len(failed), RETRY_PAUSE, attempt + 1, RETRY_ROUNDS)
        time.sleep(RETRY_PAUSE)  # 429 đến theo từng đợt, nghỉ lâu thì các bài lỗi thường qua được
        pending = failed
    rows = [(pid, lang, d, v) for (pid, lang, d), v in views.items()]
    if dry_run:
        print(rows[:3], len(targets), "bài")
        return len(rows)
    with transaction() as cur:
        written = upsert(cur, "raw.wiki_pageviews", ["place_id", "lang", "date", "views"], rows, ["place_id", "lang", "date"])
    # Thiếu dữ liệu của vài bài làm lệch xếp hạng mà không ai biết, nên quá ngưỡng thì báo lỗi để chặn bước phía sau.
    if len(failed) > max(2, int(len(targets) * MAX_FAILED_SHARE)):
        raise RuntimeError(f"{len(failed)}/{len(targets)} bài Wikipedia không lấy được lượt xem (bị giới hạn tần suất?), ví dụ {failed[:3]}")
    return written
