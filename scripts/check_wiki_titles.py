"""Kiểm tra wiki_title trong config/places.yml trước khi nạp dữ liệu.

Pageviews API chỉ đếm lượt vào đúng tên bài, nên tên là trang chuyển hướng hoặc trang định hướng sẽ cho lượt xem thấp
giả tạo. Script báo từng vấn đề: MISSING (bài không tồn tại), DISAMBIG (trang định hướng), REDIRECT (nên dùng tên đích),
LOW (lượt xem trung bình dưới ngưỡng, tín hiệu sẽ bị bỏ qua trong dbt).

    PYTHONPATH=src python scripts/check_wiki_titles.py
"""
import sys
import time
from datetime import date, timedelta
from urllib.parse import quote

from tourism.config import load_places
from tourism.http import session

MIN_AVG_VIEWS = 20
API = "https://vi.wikipedia.org/w/api.php"
PV = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/vi.wikipedia/all-access/user/{t}/daily/{s}/{e}"


def get_json(http, url, **kwargs):
    for attempt in range(6):
        r = http.get(url, timeout=30, **kwargs)
        if r.status_code == 429:
            time.sleep(4 * (attempt + 1))
            continue
        return r
    return r


def resolve(http, titles: list[str]) -> dict[str, dict]:
    """Với mỗi tiêu đề: tồn tại không, có phải trang định hướng không, đích chuyển hướng (nếu có)."""
    out = {}
    for i in range(0, len(titles), 40):
        chunk = [t.replace("_", " ") for t in titles[i : i + 40]]
        r = get_json(
            http,
            API,
            params={"action": "query", "titles": "|".join(chunk), "redirects": 1, "prop": "pageprops", "ppprop": "disambiguation",
                    "format": "json", "formatversion": 2},
        ).json()["query"]
        norm = {n["from"]: n["to"] for n in r.get("normalized", [])}
        red = {x["from"]: x["to"] for x in r.get("redirects", [])}
        pages = {p["title"]: p for p in r["pages"]}
        for t in chunk:
            n = norm.get(t, t)
            target = red.get(n, n)
            p = pages.get(target, {})
            out[t.replace(" ", "_")] = {
                "missing": p.get("missing", False),
                "disambig": "disambiguation" in p.get("pageprops", {}),
                "redirect_to": target if target != n else None,
            }
    return out


def avg_views(http, title: str) -> float | None:
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=13)
    r = get_json(http, PV.format(t=quote(title, safe=""), s=f"{start:%Y%m%d}", e=f"{end:%Y%m%d}"))
    if r.status_code != 200:
        return None
    v = [i["views"] for i in r.json()["items"]]
    return sum(v) / len(v)


def main() -> int:
    http = session()
    places = [p for p in load_places() if p.wiki_title]
    info = resolve(http, [p.wiki_title for p in places])
    problems = 0
    for p in places:
        i = info[p.wiki_title]
        flags = []
        if i["missing"]:
            flags.append("MISSING")
        if i["disambig"]:
            flags.append("DISAMBIG")
        if i["redirect_to"]:
            flags.append(f"REDIRECT -> {i['redirect_to'].replace(' ', '_')}")
        avg = None if i["missing"] else avg_views(http, i["redirect_to"] or p.wiki_title)
        if avg is not None and avg < MIN_AVG_VIEWS:
            flags.append("LOW")
        time.sleep(0.5)
        problems += bool(flags)
        avg_s = "  n/a" if avg is None else f"{avg:5.0f}"
        print(f"{p.place_id:18} tb={avg_s}  {p.wiki_title:45} {' '.join(flags)}")
    print(f"\n{problems}/{len(places)} mục cần xem lại")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
