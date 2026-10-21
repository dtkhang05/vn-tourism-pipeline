"""Xuất dữ liệu dashboard ra app/snapshot/*.parquet để đưa dashboard lên web mà không cần Postgres.

Chạy sau khi pipeline và dbt xong:  python scripts/export_snapshot.py
Biến môi trường PGHOST, PGUSER, PGPASSWORD, PGPORT, PGDATABASE dùng như dashboard (mặc định localhost/tourism).
"""
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from queries import QUERIES

HISTORY_COLS = ["as_of_date", "place_id", "hot_rank", "hot_score", "hot_rank_30d", "hot_score_30d"]


def append_history(places: pd.DataFrame, path: Path) -> None:
    """Thêm xếp hạng của ngày số liệu hiện tại vào lịch sử (mỗi ngày một lượt, chạy lại cùng ngày thì ghi đè)."""
    today = places[HISTORY_COLS].copy()
    today["as_of_date"] = pd.to_datetime(today["as_of_date"]).dt.date
    old = pd.read_parquet(path) if path.exists() else today.iloc[0:0]
    hist = pd.concat([old[~old["as_of_date"].isin(today["as_of_date"])], today], ignore_index=True)
    hist = hist.sort_values(["as_of_date", "place_id"]).reset_index(drop=True)
    hist.to_parquet(path, index=False)
    print(f"history: {hist['as_of_date'].nunique()} ngày, {len(hist)} dòng")


def main() -> None:
    url = "postgresql+psycopg2://{u}:{p}@{h}:{port}/{db}".format(
        u=os.getenv("PGUSER", "tourism"), p=os.getenv("PGPASSWORD", "tourism"), h=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"), db=os.getenv("PGDATABASE", "tourism"),
    )
    engine = create_engine(url)
    out = ROOT / "app" / "snapshot"
    out.mkdir(exist_ok=True)
    for name, sql in QUERIES.items():
        df = pd.read_sql(sql, engine)
        df.to_parquet(out / f"{name}.parquet", index=False)
        print(f"{name}: {len(df)} dòng")
        if name == "places":
            append_history(df, out / "history.parquet")


if __name__ == "__main__":
    main()
