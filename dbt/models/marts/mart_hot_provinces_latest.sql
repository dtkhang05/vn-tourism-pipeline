-- Gộp lên tỉnh/thành từ các điểm tham quan đã được xếp hạng, cho cả tuần (province_score) và tháng (province_score_30d).
--
-- Điểm tỉnh co về trung bình cả nước (shrinkage): (tổng điểm + k * trung bình toàn quốc) / (số điểm + k).
-- Tỉnh chỉ có 1 điểm không thể đứng đầu chỉ nhờ một con số; tỉnh có nhiều điểm đều nóng thì giữ được điểm cao.
-- avg_hot_score là trung bình thô, giữ lại để so sánh. Tỉnh không có điểm nào được xếp hạng trong kỳ thì hạng của kỳ đó là null.
with w as (
    select *, avg(hot_score) over () as national_avg
    from {{ ref('mart_hot_places_latest') }}
    where has_signal
),

m as (
    select *, avg(hot_score_30d) over () as national_avg
    from {{ ref('mart_hot_places_latest') }}
    where has_signal_30d
),

pw as (
    select
        province_id, province, region,
        round((sum(hot_score) + {{ var('province_prior_places') }} * max(national_avg)) / (count(*) + {{ var('province_prior_places') }}), 1) as province_score,
        round(avg(hot_score), 1)                      as avg_hot_score,
        round(max(hot_score), 1)                      as max_hot_score,
        count(*)                                      as n_places_scored,
        (array_agg(name order by hot_score desc))[1]     as top_place,
        (array_agg(place_id order by hot_score desc))[1] as top_place_id
    from w
    group by 1, 2, 3
),

pm as (
    select
        province_id, province, region,
        round((sum(hot_score_30d) + {{ var('province_prior_places') }} * max(national_avg)) / (count(*) + {{ var('province_prior_places') }}), 1) as province_score_30d,
        round(avg(hot_score_30d), 1)                  as avg_hot_score_30d,
        round(max(hot_score_30d), 1)                  as max_hot_score_30d,
        count(*)                                      as n_places_scored_30d,
        (array_agg(name order by hot_score_30d desc))[1]     as top_place_30d,
        (array_agg(place_id order by hot_score_30d desc))[1] as top_place_id_30d
    from m
    group by 1, 2, 3
),

joined as (
    select
        coalesce(pw.province_id, pm.province_id) as province_id,
        coalesce(pw.province, pm.province)       as province,
        coalesce(pw.region, pm.region)           as region,
        pw.province_score, pw.avg_hot_score, pw.max_hot_score, pw.n_places_scored, pw.top_place, pw.top_place_id,
        pm.province_score_30d, pm.avg_hot_score_30d, pm.max_hot_score_30d, pm.n_places_scored_30d, pm.top_place_30d, pm.top_place_id_30d
    from pw
    full outer join pm using (province_id)
)

select
    *,
    case when province_score is not null then rank() over (order by province_score desc nulls last) end         as hot_rank,
    case when province_score_30d is not null then rank() over (order by province_score_30d desc nulls last) end as hot_rank_30d
from joined
