FROM python:3.12-slim
RUN pip install --no-cache-dir --default-timeout=30 --retries 8 dbt-postgres==1.9.0
WORKDIR /dbt
ENTRYPOINT ["dbt"]
CMD ["build", "--profiles-dir", "."]
