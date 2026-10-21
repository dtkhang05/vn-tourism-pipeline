FROM apache/airflow:2.10.5-python3.12

# Timeout dài và tự thử lại: mạng chậm hoặc dao động không nên làm hỏng cả lần build.
ENV PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=10

# dbt chạy trong venv riêng để không xung đột phiên bản thư viện với Airflow.
# Vòng lặp thử lại vì pip không tự thử lại khi một file tải về bị hỏng (lỗi sai mã băm trên mạng không ổn định);
# dòng dbt --version cuối cùng làm build thất bại nếu cả 4 lần đều không cài được.
RUN python -m venv /home/airflow/dbt_venv \
    && for i in 1 2 3 4; do \
         /home/airflow/dbt_venv/bin/pip install --no-cache-dir dbt-postgres==1.9.0 && break; \
         echo "cai dbt that bai, thu lai lan $i"; sleep 10; \
       done \
    && /home/airflow/dbt_venv/bin/dbt --version

COPY requirements.txt /tmp/requirements.txt
RUN for i in 1 2 3 4; do \
      pip install --no-cache-dir -r /tmp/requirements.txt && break; \
      echo "cai requirements that bai, thu lai lan $i"; sleep 10; \
    done \
    && python -c "import feedparser, pytrends, psycopg2, yaml"

ENV PYTHONPATH=/opt/airflow/project/src
