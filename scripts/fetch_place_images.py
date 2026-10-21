"""Lấy ảnh đại diện cho từng điểm tham quan từ Wikimedia Commons, ghi vào config/place_images.json.

Chỉ lưu đường dẫn ảnh (thumbnail), tên tác giả và giấy phép để dashboard ghi nguồn; không tải file ảnh về.
Chỉ nhận ảnh nằm trên Commons (tự do sử dụng), bỏ qua ảnh "fair use" tải riêng lên vi.wikipedia.
Ưu tiên `image_title` trong places.yml (nếu có), nếu không dùng `wiki_title`.

    PYTHONPATH=src python scripts/fetch_place_images.py
"""
import json
import re
import sys
import time

import yaml

from tourism.config import CONFIG_DIR
from tourism.http import session

VI_API = "https://vi.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
OUT = CONFIG_DIR / "place_images.json"
TAG = re.compile(r"<[^>]+>")


def get(http, url, **params):
    params.update(format="json", formatversion=2)
    for attempt in range(6):
        r = http.get(url, params=params, timeout=30)
        if r.status_code == 429:
            time.sleep(4 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("bị giới hạn tốc độ quá lâu")


def thumbnails(http, titles: list[str]) -> dict[str, dict]:
    """Ảnh đại diện của từng bài, theo tiêu đề đã chuẩn hóa và đã theo chuyển hướng."""
    out = {}
    for i in range(0, len(titles), 40):
        chunk = [t.replace("_", " ") for t in titles[i : i + 40]]
        r = get(http, VI_API, action="query", titles="|".join(chunk), redirects=1, prop="pageimages", piprop="thumbnail|name", pithumbsize=900)["query"]
        norm = {n["from"]: n["to"] for n in r.get("normalized", [])}
        red = {x["from"]: x["to"] for x in r.get("redirects", [])}
        pages = {p["title"]: p for p in r["pages"]}
        for t in chunk:
            n = norm.get(t, t)
            out[t.replace(" ", "_")] = pages.get(red.get(n, n), {})
        time.sleep(0.5)
    return out


def licenses(http, files: list[str]) -> dict[str, dict]:
    out = {}
    for i in range(0, len(files), 40):
        chunk = files[i : i + 40]
        r = get(http, COMMONS_API, action="query", titles="|".join(f"File:{f}" for f in chunk), prop="imageinfo", iiprop="extmetadata",
                iiextmetadatafilter="LicenseShortName|Artist")["query"]
        for p in r["pages"]:
            meta = (p.get("imageinfo") or [{}])[0].get("extmetadata", {})
            out[p["title"].removeprefix("File:").replace(" ", "_")] = {
                "license": meta.get("LicenseShortName", {}).get("value", ""),
                "artist": TAG.sub("", meta.get("Artist", {}).get("value", "")).strip(),
            }
        time.sleep(0.5)
    return out


PEOPLE = re.compile(r"\b(child|children|kid|kids|girl|girls|boy|boys|woman|women|man|men|lady|people|person|portrait|selfie|couple|farmer|"
                    r"ethnic|wedding|student|students|baby|family)\b", re.IGNORECASE)


def is_photo(name: str) -> bool:
    """Chỉ nhận ảnh chụp cảnh (JPEG). Bỏ bản đồ, logo, đồ họa SVG/PNG và ảnh có dấu hiệu chụp người (nhất là trẻ em):
    ảnh quảng cáo điểm đến nên là cảnh vật, và ảnh chân dung của người lạ không phù hợp để dùng lại."""
    low = name.lower()
    return low.endswith((".jpg", ".jpeg")) and not any(w in low for w in ("map", "logo", "flag", "coat")) and not PEOPLE.search(name.replace("_", " "))


def from_commons_category(http, category: str) -> dict | None:
    """Ảnh JPEG đầu tiên trong danh mục Commons của địa điểm, dùng khi bài Wikipedia không có ảnh đại diện phù hợp."""
    members = get(http, COMMONS_API, action="query", list="categorymembers", cmtitle=f"Category:{category}", cmtype="file", cmlimit=40)["query"]["categorymembers"]
    for m in members:
        name = m["title"].removeprefix("File:")
        if not is_photo(name):
            continue
        info = get(http, COMMONS_API, action="query", titles=m["title"], prop="imageinfo", iiprop="url|extmetadata", iiurlwidth=900,
                   iiextmetadatafilter="LicenseShortName|Artist")["query"]["pages"][0].get("imageinfo", [{}])[0]
        if not info.get("thumburl"):
            continue
        meta = info.get("extmetadata", {})
        return {
            "url": info["thumburl"].split("?")[0], "file": name, "page": info.get("descriptionurl", ""),
            "license": meta.get("LicenseShortName", {}).get("value", ""),
            "artist": TAG.sub("", meta.get("Artist", {}).get("value", "")).strip(),
        }
    return None


def main() -> int:
    places = yaml.safe_load((CONFIG_DIR / "places.yml").read_text(encoding="utf-8"))["places"]
    want = {p["id"]: p.get("image_title") or p["wiki_title"] for p in places}
    http = session()
    thumbs = thumbnails(http, list(set(want.values())))
    chosen = {}
    for pid, title in want.items():
        page = thumbs.get(title, {})
        src = page.get("thumbnail", {}).get("source", "")
        name = page.get("pageimage", "")
        if "/wikipedia/commons/" in src and is_photo(name):
            chosen[pid] = {"url": src.split("?")[0], "file": name, "page": f"https://vi.wikipedia.org/wiki/{page['title'].replace(' ', '_')}"}
    lic = licenses(http, sorted({c["file"] for c in chosen.values()}))
    for c in chosen.values():
        info = lic.get(c["file"].replace(" ", "_"), {})
        c["license"] = info.get("license", "")
        c["artist"] = info.get("artist", "")
    # Điểm chưa có ảnh: thử danh mục Commons nếu places.yml khai báo `commons_category`.
    for p in places:
        if p["id"] not in chosen and p.get("commons_category"):
            found = from_commons_category(http, p["commons_category"])
            if found:
                chosen[p["id"]] = found
            time.sleep(0.5)
    OUT.write_text(json.dumps(dict(sorted(chosen.items())), ensure_ascii=False, indent=1), encoding="utf-8")
    missing = [pid for pid in want if pid not in chosen]
    print(f"{len(chosen)}/{len(want)} điểm có ảnh Commons. Thiếu ảnh: {', '.join(missing) or 'không'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
