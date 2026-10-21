-- Một dòng cho mỗi (bài báo, địa điểm). Ngày tính theo giờ Việt Nam.
select
    m.article_url,
    m.place_id,
    m.in_title,
    a.source,
    a.title,
    (a.published_at at time zone 'Asia/Ho_Chi_Minh')::date as published_date,
    a.published_at
from {{ source('raw', 'news_place_mentions') }} m
join {{ source('raw', 'news_articles') }} a on a.url = m.article_url
where a.published_at is not null
