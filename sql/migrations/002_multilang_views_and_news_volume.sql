-- Lượt xem Wikipedia theo từng ngôn ngữ (vi = khách trong nước, en/ko/zh/ja = khách quốc tế) và số bài báo theo tuần.
-- Chạy: docker compose exec -T postgres psql -U tourism -d tourism < sql/migrations/002_multilang_views_and_news_volume.sql
ALTER TABLE raw.wiki_pageviews ADD COLUMN IF NOT EXISTS lang text NOT NULL DEFAULT 'vi';
ALTER TABLE raw.wiki_pageviews DROP CONSTRAINT IF EXISTS wiki_pageviews_pkey;
ALTER TABLE raw.wiki_pageviews ADD PRIMARY KEY (place_id, lang, date);

CREATE TABLE IF NOT EXISTS raw.place_wiki_titles (
    place_id  text NOT NULL REFERENCES raw.places (place_id),
    lang      text NOT NULL,
    title     text NOT NULL,
    PRIMARY KEY (place_id, lang, title)
);

CREATE TABLE IF NOT EXISTS raw.news_volume (
    place_id      text NOT NULL REFERENCES raw.places (place_id),
    window_start  date NOT NULL,      -- cửa sổ 7 ngày [window_start, window_start + 7)
    articles      integer NOT NULL,
    fetched_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (place_id, window_start)
);
