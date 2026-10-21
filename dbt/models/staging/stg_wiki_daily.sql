-- Lượt xem Wikipedia mỗi (địa điểm, ngày), tách khách trong nước (bài tiếng Việt) và khách quốc tế (en, ko, zh, ja).
select
    place_id,
    date,
    sum(views) filter (where lang = 'vi')  as vi_views,
    sum(views) filter (where lang <> 'vi') as intl_views,
    sum(views)                             as total_views
from {{ source('raw', 'wiki_pageviews') }}
group by 1, 2
