-- Hồi quy cho lỗi thật đã gặp: Mũi Cà Mau từng đứng hạng 1 chỉ vì một ngày đột biến (72 lượt xem trên mức nền ~20).
-- Một địa điểm có mức quan tâm thuộc nhóm thấp nhất (dưới phân vị 25) không được đứng trong top 10, cả theo tuần lẫn theo tháng.
-- Phân vị tính trong đúng tập điểm đang được xếp hạng của từng loại: điểm có tín hiệu tuần và điểm có tín hiệu tháng không trùng nhau
-- (ví dụ điểm mới đủ lịch sử cho tháng nhưng chưa đủ cho tuần), nên dùng chung một tập sẽ làm lệch phân vị và báo lỗi nhầm.
with week as (
    select place_id, hot_rank, level_7d,
           percent_rank() over (order by level_7d) as level_pct
    from {{ ref('mart_hot_places_latest') }}
    where has_signal
),
month as (
    select place_id, hot_rank_30d, level_30d,
           percent_rank() over (order by level_30d) as level_pct
    from {{ ref('mart_hot_places_latest') }}
    where has_signal_30d
)
select place_id, hot_rank, level_7d, 'tuan' as kind from week where hot_rank <= 10 and level_pct < 0.25
union all
select place_id, hot_rank_30d, level_30d, 'thang' from month where hot_rank_30d <= 10 and level_pct < 0.25
