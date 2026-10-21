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


if __name__ == "__main__":
    main()
