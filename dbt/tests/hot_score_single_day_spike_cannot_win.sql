-- Hồi quy cho lỗi thật đã gặp: Mũi Cà Mau từng đứng hạng 1 chỉ vì một ngày đột biến (72 lượt xem trên mức nền ~20).
-- Một địa điểm có mức quan tâm thuộc nhóm thấp nhất (dưới phân vị 25) không được đứng trong top 10, cả theo tuần lẫn theo tháng.
with ranked as (
    select place_id, hot_rank, hot_rank_30d, level_7d, level_30d,
           percent_rank() over (order by level_7d)  as level_pct_week,
           percent_rank() over (order by level_30d) as level_pct_month
    from {{ ref('mart_hot_places_latest') }}
    where has_signal
)
select place_id, hot_rank, level_7d, 'tuan' as kind from ranked where hot_rank <= 10 and level_pct_week < 0.25
union all
select place_id, hot_rank_30d, level_30d, 'thang' from ranked where hot_rank_30d <= 10 and level_pct_month < 0.25
