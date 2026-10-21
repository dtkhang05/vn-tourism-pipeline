-- Điểm tham quan kèm tỉnh/thành và miền.
select
    p.place_id,
    p.name,
    p.province_id,
    pr.name   as province,
    pr.region as region,
    p.lat,
    p.lon
from {{ source('raw', 'places') }} p
join {{ source('raw', 'provinces') }} pr using (province_id)
