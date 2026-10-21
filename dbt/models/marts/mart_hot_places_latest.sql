-- Bảng cho dashboard: một dòng cho mỗi điểm tham quan, với điểm nóng theo tuần (hot_score, hot_rank, level_7d...) và theo tháng
-- (hot_score_30d, hot_rank_30d, level_30d...), mỗi loại lấy theo ngày mới nhất đã có số liệu Wikipedia.
-- Điểm chưa có số liệu vẫn có mặt với has_signal = false và hạng = null.
with latest_w as (select max(date) as d from {{ ref('fct_hot_score') }}),
     latest_m as (select max(date) as d from {{ ref('fct_hot_score_month') }}),

cur_w as (select h.* from {{ ref('fct_hot_score') }} h join latest_w on h.date = latest_w.d),
cur_m as (select h.* from {{ ref('fct_hot_score_month') }} h join latest_m on h.date = latest_m.d),

-- Lượt xem Wikipedia thấp hẳn vào cuối tuần là dấu hiệu tra cứu học tập hoặc công việc hơn là quan tâm du lịch
-- (người đang lên kế hoạch đi chơi cũng tra cứu vào cuối tuần). Tỉ lệ này cho dashboard thấy độ tin cậy của tín hiệu.
dow as (
    select place_id,
           avg(wiki_views) filter (where extract(isodow from date) <= 5) as weekday_avg,
           avg(wiki_views) filter (where extract(isodow from date) >= 6) as weekend_avg
    from {{ ref('fct_place_daily_signals') }}
    where wiki_views is not null
      and date > (select d from latest_w) - 28 and date <= (select d from latest_w)
    group by 1
),

joined as (
    select
        p.place_id, p.name, p.province_id, p.province, p.region, p.lat, p.lon,
        (select d from latest_w)  as as_of_date,
        w.hot_score, w.level as level_7d, w.vi_level as vi_7d, w.intl_level as intl_7d, w.base as base_28d, w.ly_level as ly_7d,
        w.change_pct, w.yoy_pct, w.intl_yoy_pct, w.n_signals,
        w.p_attention, w.p_yoy, w.p_intl, w.p_news,
        coalesce(w.news_recent, 0) as news_7d, w.news_base as news_base_7d,
        (w.hot_score is not null)  as has_signal,
        m.hot_score as hot_score_30d, m.level as level_30d, m.vi_level as vi_30d, m.intl_level as intl_30d, m.base as base_30d,
        m.ly_level as ly_30d, m.change_pct as change_pct_30d, m.yoy_pct as yoy_pct_30d, m.intl_yoy_pct as intl_yoy_pct_30d, m.n_signals as n_signals_30d,
        m.p_attention as p_attention_30d, m.p_yoy as p_yoy_30d, m.p_intl as p_intl_30d, m.p_news as p_news_30d,
        coalesce(m.news_recent, 0) as news_30d, m.news_base as news_base_30d,
        (m.hot_score is not null)  as has_signal_30d,
        round((d.weekday_avg / nullif(d.weekend_avg, 0))::numeric, 1) as weekday_weekend_ratio
    from {{ ref('stg_places') }} p
    left join cur_w w using (place_id)
    left join cur_m m using (place_id)
    left join dow d using (place_id)
)

select
    *,
    case when has_signal then rank() over (order by hot_score desc nulls last, level_7d desc nulls last) end as hot_rank,
    case when has_signal_30d then rank() over (order by hot_score_30d desc nulls last, level_30d desc nulls last) end as hot_rank_30d
from joined
