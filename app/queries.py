"""Các truy vấn dashboard dùng; scripts/export_snapshot.py chạy lại đúng các truy vấn này để tạo ảnh chụp dữ liệu."""

QUERIES = {
    "places": "select * from marts.mart_hot_places_latest",
    "provinces": "select * from marts.mart_hot_provinces_latest",
    "weather": (
        "select place_id, avg(temp_max_c) as temp, sum(precip_mm) as rain from raw.weather_daily "
        "where date between current_date and current_date + 2 group by 1"
    ),
    "ingest_runs": (
        "select distinct on (source) source as \"Nguồn\", finished_at as \"Lần chạy gần nhất\", status as \"Trạng thái\", rows_written as \"Số dòng\" "
        "from raw.ingest_runs order by source, finished_at desc"
    ),
}
