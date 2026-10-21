-- Một dòng cho mỗi (địa điểm, ngày) trong 90 ngày gần nhất, gộp mọi tín hiệu về cùng một grain.
-- wiki_views = tổng lượt xem mọi ngôn ngữ; chỉ có khi bài tiếng Việt đã có số liệu ngày đó (Wikipedia trễ ~1 ngày).
-- wiki_views_ly = cùng ngày của năm trước, lùi đúng 364 ngày (52 tuần) để trùng thứ trong tuần.
with spine as (
    select p.place_id, d::date as date
    from {{ ref('stg_places') }} p
    cross join generate_series(
        (now() at time zone 'Asia/Ho_Chi_Minh')::date - 89,
        (now() at time zone 'Asia/Ho_Chi_Minh')::date,
        interval '1 day'
    ) d
),

news as (
    select place_id, published_date as date,
           count(*) as news_count,
           count(*) filter (where in_title) as news_title_count
    from {{ ref('stg_news_mentions') }}
    group by 1, 2
)

select
    s.place_id,
    s.date,
    coalesce(n.news_count, 0)        as news_count,
    coalesce(n.news_title_count, 0)  as news_title_count,
    case when w.vi_views is not null then w.total_views end as wiki_views,
    w.vi_views,
    case when w.vi_views is not null then coalesce(w.intl_views, 0) end as intl_views,
    ly.total_views                   as wiki_views_ly,
    case when ly.vi_views is not null then coalesce(ly.intl_views, 0) end as intl_views_ly,
    t.interest_avg                   as trends_interest,
    wx.temp_max_c,
    wx.precip_mm
from spine s
left join news n on n.place_id = s.place_id and n.date = s.date
left join {{ ref('stg_wiki_daily') }} w on w.place_id = s.place_id and w.date = s.date
left join {{ ref('stg_wiki_daily') }} ly on ly.place_id = s.place_id and ly.date = s.date - 364
left join {{ ref('stg_trends_daily') }} t on t.place_id = s.place_id and t.date = s.date
left join {{ source('raw', 'weather_daily') }} wx on wx.place_id = s.place_id and wx.date = s.date
