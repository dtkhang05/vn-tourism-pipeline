-- Schema raw: dữ liệu thô từ các nguồn, ghi theo kiểu upsert để pipeline chạy lại an toàn (idempotent).
\connect tourism

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;

CREATE TABLE IF NOT EXISTS raw.provinces (
    province_id  text PRIMARY KEY,
    name         text NOT NULL,
    region       text NOT NULL            -- Miền Bắc | Miền Trung | Miền Nam
);

-- Điểm tham quan cụ thể; mỗi điểm thuộc đúng một tỉnh/thành.
CREATE TABLE IF NOT EXISTS raw.places (
    place_id        text PRIMARY KEY,
    name            text NOT NULL,
    province_id     text NOT NULL REFERENCES raw.provinces (province_id),
    lat             double precision NOT NULL,
    lon             double precision NOT NULL,
    wiki_title      text,
    trends_keyword  text
);

CREATE TABLE IF NOT EXISTS raw.news_articles (
    url                    text PRIMARY KEY,
    source                 text NOT NULL,
    title                  text NOT NULL,
    summary                text,
    published_at           timestamptz,
    fetched_at             timestamptz NOT NULL DEFAULT now(),
    mentions_extracted_at  timestamptz
);

CREATE TABLE IF NOT EXISTS raw.news_place_mentions (
    article_url  text NOT NULL REFERENCES raw.news_articles (url) ON DELETE CASCADE,
    place_id     text NOT NULL REFERENCES raw.places (place_id),
    in_title     boolean NOT NULL,
    PRIMARY KEY (article_url, place_id)
);

-- Lượt xem bài Wikipedia theo ngôn ngữ: vi = khách trong nước; en, ko, zh, ja = khách quốc tế.
CREATE TABLE IF NOT EXISTS raw.wiki_pageviews (
    place_id    text NOT NULL REFERENCES raw.places (place_id),
    lang        text NOT NULL DEFAULT 'vi',
    date        date NOT NULL,
    views       integer NOT NULL,
    fetched_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (place_id, lang, date)
);

-- Tên bài ở từng ngôn ngữ, lấy tự động từ liên kết ngôn ngữ của bài tiếng Việt.
CREATE TABLE IF NOT EXISTS raw.place_wiki_titles (
    place_id  text NOT NULL REFERENCES raw.places (place_id),
    lang      text NOT NULL,
    title     text NOT NULL,
    PRIMARY KEY (place_id, lang, title)
);

-- Số bài báo nhắc địa điểm trong từng cửa sổ 7 ngày (Google News RSS), có lịch sử ngay từ lần chạy đầu.
CREATE TABLE IF NOT EXISTS raw.news_volume (
    place_id      text NOT NULL REFERENCES raw.places (place_id),
    window_start  date NOT NULL,
    articles      integer NOT NULL,
    fetched_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (place_id, window_start)
);

CREATE TABLE IF NOT EXISTS raw.trends_interest (
    place_id    text NOT NULL REFERENCES raw.places (place_id),
    ts          timestamptz NOT NULL,
    interest    integer NOT NULL,  -- 0-100, đã chuẩn hóa theo từ khóa neo trong cùng một lô
    fetched_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (place_id, ts)
);

CREATE TABLE IF NOT EXISTS raw.weather_daily (
    place_id    text NOT NULL REFERENCES raw.places (place_id),
    date        date NOT NULL,
    temp_max_c  real,
    precip_mm   real,
    fetched_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (place_id, date)
);

CREATE TABLE IF NOT EXISTS raw.ingest_runs (
    id           bigserial PRIMARY KEY,
    source       text NOT NULL,
    started_at   timestamptz NOT NULL,
    finished_at  timestamptz NOT NULL DEFAULT now(),
    rows_written integer NOT NULL,
    status       text NOT NULL,     -- ok | empty (0 dòng, nguồn có thể đang chặn) | error
    error        text
);
