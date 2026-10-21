"""Nhận diện địa danh trong văn bản tiếng Việt.

Chuẩn hóa: bỏ dấu, hạ chữ thường, thay ký tự không phải chữ/số bằng khoảng trắng.
Sau đó so khớp alias theo ranh giới từ, nên "Đà Lạt" và "da lat" đều khớp,
còn "Sapa" không khớp nhầm trong từ dài hơn.
"""
import re
import unicodedata
from dataclasses import dataclass

from tourism.config import Place


def normalize(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return f" {text.strip()} "


@dataclass(frozen=True)
class Mention:
    place_id: str
    in_title: bool


class PlaceMatcher:
    def __init__(self, places: list[Place]):
        self._patterns: list[tuple[str, str]] = []
        for p in places:
            for alias in p.aliases:
                self._patterns.append((p.place_id, normalize(alias)))

    def find(self, title: str, summary: str = "") -> list[Mention]:
        title_n, body_n = normalize(title), normalize(summary or "")
        found: dict[str, bool] = {}
        for place_id, pattern in self._patterns:
            in_title = pattern in title_n
            if in_title or pattern in body_n:
                found[place_id] = found.get(place_id, False) or in_title
        return [Mention(pid, t) for pid, t in found.items()]
