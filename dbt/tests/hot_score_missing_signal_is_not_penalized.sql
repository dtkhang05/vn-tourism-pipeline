-- Hồi quy cho cả điểm tuần và điểm tháng: điểm nóng luôn trong [0, 100];
-- số tín hiệu có mặt nằm trong [1, 4]; tăng trưởng so với năm trước chỉ có khi có đủ dữ liệu cùng kỳ.
select 'tuan' as kind, place_id, date
from {{ ref('fct_hot_score') }}
where hot_score < 0 or hot_score > 100
   or n_signals < 1 or n_signals > 4
   or (yoy is not null and ly_level is null)
   or (intl_yoy is not null and intl_ly_level is null)
union all
select 'thang', place_id, date
from {{ ref('fct_hot_score_month') }}
where hot_score < 0 or hot_score > 100
   or n_signals < 1 or n_signals > 4
   or (yoy is not null and ly_level is null)
   or (intl_yoy is not null and intl_ly_level is null)
