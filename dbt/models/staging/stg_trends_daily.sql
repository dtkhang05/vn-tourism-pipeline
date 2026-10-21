-- Dữ liệu Trends theo giờ gộp thành trung bình theo ngày (giờ Việt Nam).
select
    place_id,
    (ts at time zone 'Asia/Ho_Chi_Minh')::date as date,
    avg(interest)::numeric(8, 2) as interest_avg
from {{ source('raw', 'trends_interest') }}
group by 1, 2
