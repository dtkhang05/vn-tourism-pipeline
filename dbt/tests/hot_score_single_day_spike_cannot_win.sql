-- Hồi quy cho lỗi thật đã gặp: Mũi Cà Mau từng đứng hạng 1 chỉ vì một ngày đột biến (72 lượt xem trên mức nền ~20).
-- Một địa điểm có mức quan tâm thuộc nhóm thấp nhất không được đứng trong top 10, cả theo tuần lẫn theo tháng.
-- Cổng trong macro cắt ở phân vị 25; test dùng ngưỡng 15 làm biên đệm vì mart làm tròn level còn 1 chữ số, tạo các giá trị bằng nhau
-- và làm phân vị lệch vài phần trăm so với cổng. Điểm sát ranh (như Mũi Né, ~0,24) là hợp lệ; lỗi thật nằm sâu trong nhóm thấp.
-- Phân vị phải tính trên TOÀN BỘ điểm có số liệu, đúng tập mà cổng min_attention_pct trong macro dùng. Nếu chỉ tính trong số điểm đã
-- được xếp hạng thì điểm thấp nhất của nhóm đã lọc luôn rơi xuống dưới phân vị 25 của nhóm đó và test báo lỗi nhầm.
with week as (
    select place_id, hot_rank, level_7d,
           percent_rank() over (order by level_7d) as level_pct
    from {{ ref('mart_hot_places_latest') }}
    where level_7d is not null
),
month as (
    select place_id, hot_rank_30d, level_30d,
           percent_rank() over (order by level_30d) as level_pct
    from {{ ref('mart_hot_places_latest') }}
    where level_30d is not null
)
select place_id, hot_rank, level_7d, 'tuan' as kind from week where hot_rank <= 10 and level_pct < 0.15
union all
select place_id, hot_rank_30d, level_30d, 'thang' from month where hot_rank_30d <= 10 and level_pct < 0.15
