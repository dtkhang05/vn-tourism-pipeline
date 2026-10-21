FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir --default-timeout=120 --retries 10 streamlit pandas pydeck sqlalchemy psycopg2-binary
COPY app /app
COPY .streamlit /app/.streamlit
COPY config/place_images.json /app/place_images.json
CMD ["streamlit", "run", "dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]
