"""DAG chính: thu thập song song -> trích địa danh -> dbt run -> dbt test.

Chạy mỗi 3 giờ. Mọi bước ghi theo kiểu upsert nên có thể chạy lại hoặc backfill an toàn.
Nguồn Google Trends là tùy chọn: lỗi ở đó không chặn các bước phía sau (trigger_rule).
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator

DBT = "/home/airflow/dbt_venv/bin/dbt"
DBT_ARGS = "--project-dir /opt/airflow/project/dbt --profiles-dir /opt/airflow/project/dbt --log-path /tmp/dbt_logs --target-path /tmp/dbt_target"  # thư mục dbt gắn từ máy chủ không ghi được


def _ingest(source: str):
    # Chỉ nhận `source`: nếu có **kwargs thì Airflow nhồi cả ngữ cảnh (conf, ds...) xuống run() và gây TypeError.
    from tourism.cli import run_source

    return run_source(source, dry_run=False)


def _load_places():
    from tourism.cli import load_places_table

    return load_places_table()


default_args = {
    "owner": "data-eng",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="tourism_hot_places",
    description="Thu thập tín hiệu du lịch Việt Nam và tính hot score",
    schedule="0 */3 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["tourism"],
) as dag:
    load_places = PythonOperator(task_id="load_places", python_callable=_load_places)

    news = PythonOperator(task_id="ingest_news", python_callable=_ingest, op_kwargs={"source": "news"})
    wiki = PythonOperator(task_id="ingest_wiki", python_callable=_ingest, op_kwargs={"source": "wiki"})
    gnews = PythonOperator(task_id="ingest_news_volume", python_callable=_ingest, op_kwargs={"source": "gnews"})
    weather = PythonOperator(task_id="ingest_weather", python_callable=_ingest, op_kwargs={"source": "weather"})
    trends = PythonOperator(
        task_id="ingest_trends",
        python_callable=_ingest,
        op_kwargs={"source": "trends"},
        retries=0,
    )
    mentions = PythonOperator(task_id="extract_mentions", python_callable=_ingest, op_kwargs={"source": "mentions"})

    ingested = EmptyOperator(task_id="ingested", trigger_rule="all_done")
    dbt_run = BashOperator(task_id="dbt_run", bash_command=f"{DBT} run {DBT_ARGS}")
    dbt_test = BashOperator(task_id="dbt_test", bash_command=f"{DBT} test {DBT_ARGS}")

    load_places >> [news, wiki, gnews, weather, trends]
    news >> mentions
    [mentions, wiki, gnews, weather, trends] >> ingested >> dbt_run >> dbt_test
