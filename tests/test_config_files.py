import json

import yaml

from tourism.config import CONFIG_DIR, load_places

ALLOWED_PLACE_KEYS = {"id", "name", "province", "lat", "lon", "wiki_title", "trends_keyword", "aliases", "image_title", "commons_category", "extra_wiki_titles"}


def test_places_yml_has_only_known_keys():
    # Bắt lỗi YAML dạng {a: x, b: Tên (A, B)}: dấu phẩy trong giá trị không đặt nháy sẽ tách thành khóa lạ.
    raw = yaml.safe_load((CONFIG_DIR / "places.yml").read_text(encoding="utf-8"))["places"]
    for p in raw:
        assert set(p) <= ALLOWED_PLACE_KEYS, f"{p['id']}: khóa lạ {set(p) - ALLOWED_PLACE_KEYS}"


def test_place_images_are_attributed_and_match_known_places():
    path = CONFIG_DIR / "place_images.json"
    images = json.loads(path.read_text(encoding="utf-8"))
    ids = {p.place_id for p in load_places()}
    assert set(images) <= ids, f"ảnh của điểm không tồn tại: {set(images) - ids}"
    for pid, img in images.items():
        assert img["url"].startswith(("https://upload.wikimedia.org/", "https://thumb.wikimedia.org/")), pid
        assert img["url"].lower().endswith((".jpg", ".jpeg")), f"{pid}: không phải ảnh JPEG"
        assert img["license"], f"{pid}: thiếu giấy phép, không được dùng khi chưa ghi nguồn"
        assert img["artist"], f"{pid}: thiếu tên tác giả"
