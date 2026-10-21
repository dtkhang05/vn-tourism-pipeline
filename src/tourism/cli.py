"""Điểm vào dòng lệnh: python -m tourism.cli <lệnh> [--dry-run]"""
import argparse
import importlib
import logging
import sys

from tourism.config import load_places, load_provinces
from tourism.db import log_run, transaction, upsert, utcnow

SOURCES = {
    "news": "tourism.ingest.news",
    "wiki": "tourism.ingest.wikipedia",
    "gnews": "tourism.ingest.news_volume",
    "trends": "tourism.ingest.trends",
    "weather": "tourism.ingest.weather",
    "mentions": "tourism.ingest.mentions",
}


def load_places_table() -> int:
    provinces = [(p.province_id, p.name, p.region) for p in load_provinces()]
    places = [(p.place_id, p.name, p.province_id, p.lat, p.lon, p.wiki_title, p.trends_keyword) for p in load_places()]
    with transaction() as cur:
        upsert(cur, "raw.provinces", ["province_id", "name", "region"], provinces, ["province_id"])
        return upsert(
            cur,
            "raw.places",
            ["place_id", "name", "province_id", "lat", "lon", "wiki_title", "trends_keyword"],
            places,
            ["place_id"],
        )


def run_source(name: str, dry_run: bool, **kwargs) -> int:
    module = importlib.import_module(SOURCES[name])
    started = utcnow()
    try:
        rows = module.run(dry_run=dry_run, **kwargs)
    except Exception as exc:
        if not dry_run:
            log_run(name, started, 0, "error", str(exc)[:500])
        raise
    if not dry_run:
        # 0 dòng không phải lỗi nhưng cũng không phải thành công: nguồn có thể đang chặn (ví dụ Google Trends 429)
        log_run(name, started, rows, "ok" if rows or name == "mentions" else "empty")
    logging.getLogger("tourism").info("%s: %d dòng", name, rows)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tourism")
    parser.add_argument("command", choices=["load-places", "all", *SOURCES])
    parser.add_argument("--dry-run", action="store_true", help="chỉ gọi nguồn dữ liệu, không ghi database")
    parser.add_argument("--days", type=int, default=None, help="số ngày lấy lại (wiki; với gnews, trên 14 nghĩa là backfill 8 tuần)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.command == "load-places":
        print(load_places_table())
    elif args.command == "all":
        load_places_table()
        for name in ("news", "mentions", "wiki", "gnews", "weather", "trends"):
            run_source(name, args.dry_run)
    else:
        kwargs = {"days": args.days} if args.command in ("wiki", "gnews") and args.days else {}
        run_source(args.command, args.dry_run, **kwargs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
