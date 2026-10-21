import os
from contextlib import contextmanager
from datetime import UTC, datetime

import psycopg2
from psycopg2.extras import execute_values


def get_conn():
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
        dbname=os.getenv("PGDATABASE", "tourism"),
        user=os.getenv("PGUSER", "tourism"),
        password=os.getenv("PGPASSWORD", "tourism"),
    )


@contextmanager
def transaction():
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


def upsert(cur, table: str, columns: list[str], rows: list[tuple], conflict: list[str]) -> int:
    """INSERT ... ON CONFLICT DO UPDATE. Chạy lại cùng dữ liệu không tạo bản ghi trùng."""
    if not rows:
        return 0
    updates = [c for c in columns if c not in conflict]
    set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in updates) or f"{conflict[0]} = EXCLUDED.{conflict[0]}"
    sql = (
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s "
        f"ON CONFLICT ({', '.join(conflict)}) DO UPDATE SET {set_clause}"
    )
    execute_values(cur, sql, rows)
    return len(rows)


def log_run(source: str, started_at: datetime, rows: int, status: str, error: str | None = None) -> None:
    with transaction() as cur:
        cur.execute(
            "INSERT INTO raw.ingest_runs (source, started_at, rows_written, status, error) "
            "VALUES (%s, %s, %s, %s, %s)",
            (source, started_at, rows, status, error),
        )


def utcnow() -> datetime:
    return datetime.now(UTC)
