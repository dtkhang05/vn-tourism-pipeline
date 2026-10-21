-- Grain của fct_place_daily_signals phải là (place_id, date); join sai sẽ làm nhân đôi dòng.
select place_id, date, count(*) as n
from {{ ref('fct_place_daily_signals') }}
group by 1, 2
having count(*) > 1
