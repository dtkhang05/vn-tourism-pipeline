-- Chuyển DB đã có từ mô hình "địa điểm cấp thành phố/tỉnh" sang mô hình hai tầng: tỉnh/thành -> điểm tham quan.
-- Chạy một lần:  docker compose exec -T postgres psql -U tourism -d tourism < sql/migrations/001_place_hierarchy.sql
--
-- Bộ địa điểm cũ bị thay hoàn toàn nên dữ liệu phụ thuộc vào nó (lượt xem, thời tiết, lượt nhắc) bị xóa và nạp lại.
-- Bài báo gốc (raw.news_articles) được giữ nguyên và chỉ đánh dấu để trích địa danh lại theo danh sách mới.
-- Các schema staging/marts chỉ chứa dữ liệu dẫn xuất nên xóa đi và để dbt dựng lại.
BEGIN;

DROP SCHEMA IF EXISTS staging CASCADE;
DROP SCHEMA IF EXISTS marts CASCADE;
CREATE SCHEMA staging;
CREATE SCHEMA marts;

CREATE TABLE IF NOT EXISTS raw.provinces (
    province_id  text PRIMARY KEY,
    name         text NOT NULL,
    region       text NOT NULL
);

TRUNCATE raw.news_place_mentions, raw.wiki_pageviews, raw.trends_interest, raw.weather_daily;
DELETE FROM raw.places;

ALTER TABLE raw.places DROP COLUMN IF EXISTS province;
ALTER TABLE raw.places ADD COLUMN IF NOT EXISTS province_id text NOT NULL REFERENCES raw.provinces (province_id);

UPDATE raw.news_articles SET mentions_extracted_at = NULL;

COMMIT;
