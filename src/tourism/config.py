import os
from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_DIR = Path(os.getenv("CONFIG_DIR", Path(__file__).resolve().parents[2] / "config"))


@dataclass(frozen=True)
class Province:
    province_id: str
    name: str
    region: str


@dataclass(frozen=True)
class Place:
    place_id: str
    name: str
    province_id: str
    lat: float
    lon: float
    wiki_title: str | None
    trends_keyword: str | None
    aliases: tuple[str, ...]
    extra_wiki_titles: tuple[str, ...] = ()  # bài khác cùng chủ đề (bài bị đổi tên hoặc tách trang), lượt xem được cộng chung


def _read_places_file() -> dict:
    return yaml.safe_load((CONFIG_DIR / "places.yml").read_text(encoding="utf-8"))


def load_provinces() -> list[Province]:
    return [Province(p["id"], p["name"], p["region"]) for p in _read_places_file()["provinces"]]


def load_places() -> list[Place]:
    return [
        Place(
            place_id=p["id"],
            name=p["name"],
            province_id=p["province"],
            lat=p["lat"],
            lon=p["lon"],
            wiki_title=p.get("wiki_title"),
            trends_keyword=p.get("trends_keyword"),
            aliases=tuple(p.get("aliases", [p["name"]])),
            extra_wiki_titles=tuple(p.get("extra_wiki_titles", [])),
        )
        for p in _read_places_file()["places"]
    ]


def load_news_feeds() -> list[dict]:
    raw = yaml.safe_load((CONFIG_DIR / "sources.yml").read_text(encoding="utf-8"))
    return raw["news_feeds"]
