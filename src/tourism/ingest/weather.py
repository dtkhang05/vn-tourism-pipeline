import logging
from datetime import date

from tourism.config import load_places
from tourism.db import transaction, upsert
from tourism.http import session

log = logging.getLogger(__name__)
API = "https://api.open-meteo.com/v1/forecast"


def fetch_weather(lat: float, lon: float) -> list[tuple[date, float | None, float | None]]:
    resp = session().get(
        API,
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,precipitation_sum",
            "past_days": 3,
            "forecast_days": 3,
            "timezone": "Asia/Bangkok",
        },
        timeout=30,
    )
    resp.raise_for_status()
    d = resp.json()["daily"]
    return [
        (date.fromisoformat(t), tmax, rain)
        for t, tmax, rain in zip(d["time"], d["temperature_2m_max"], d["precipitation_sum"])
    ]


def run(dry_run: bool = False) -> int:
    rows: list[tuple] = []
    for p in load_places():
        try:
            rows.extend((p.place_id, d, t, r) for d, t, r in fetch_weather(p.lat, p.lon))
        except Exception as exc:  # noqa: BLE001 - một địa điểm lỗi không làm hỏng cả lô
            log.warning("Bỏ qua %s: %s", p.place_id, exc)
    if dry_run:
        print(rows[:3])
        return len(rows)
    with transaction() as cur:
        return upsert(cur, "raw.weather_daily", ["place_id", "date", "temp_max_c", "precip_mm"], rows, ["place_id", "date"])
