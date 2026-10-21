{#
  Điểm nóng (0-100) cho mỗi (địa điểm, ngày), dùng chung cho xếp hạng tuần và tháng.
  Bốn tín hiệu, mỗi tín hiệu xếp hạng phần trăm giữa các địa điểm cùng ngày, rồi lấy trung bình với trọng số BẰNG NHAU
  (không có trọng số nào để chỉnh tay cho ra thứ hạng "đẹp"):
    attention : quy mô quan tâm = lượt xem Wikipedia (mọi ngôn ngữ) trung bình recent_days ngày gần nhất
    yoy       : tăng trưởng so với CÙNG KỲ NĂM TRƯỚC = ln((TB hiện tại + K) / (TB cùng kỳ năm trước + K)); loại bỏ yếu tố mùa vụ
                (Hạ Long luôn đông vào hè, Hồ Gươm luôn tăng khi bài "Sự tích Hồ Gươm" vào chương trình học)
    intl_yoy  : như yoy nhưng chỉ tính lượt xem bài tiếng Anh, Hàn, Trung, Nhật. Người đọc các bản này chủ yếu là khách sắp đi du lịch,
                không bị lịch học và lịch làm việc ở Việt Nam chi phối
    news      : tăng trưởng độ phủ báo chí (Google News) giữa recent_days ngày gần nhất và 4 tuần trước đó; chỉ có ở ngày mới nhất
  Xu hướng ngắn hạn (so với giai đoạn ngay trước) KHÔNG nằm trong điểm vì bị mùa vụ và lịch học làm nhiễu; vẫn xuất change_pct để hiển thị.
  Mức tăng hoặc giảm quá yoy_max_ratio lần so với năm trước bị coi là không đáng tin (thường do bài bị đổi tên hoặc tách trang) và bỏ khỏi điểm.
  Điều kiện xếp hạng: lượng quan tâm không thuộc nhóm thấp nhất (min_attention_pct) và có ít nhất min_signals tín hiệu.
  Vì dùng trung bình nhiều ngày và xếp hạng phần trăm nên một ngày đột biến không thể áp đảo bảng xếp hạng.
  Tín hiệu thiếu là NULL và bị loại khỏi trung bình (chia cho số tín hiệu có mặt, n_signals), không bị tính thành 0.

  recent_days / baseline_days: cửa sổ gần đây và cửa sổ nền ngay trước đó (tuần: 7/28, tháng: 30/30); cửa sổ nền chỉ dùng cho change_pct.
  min_baseline: số ngày có số liệu tối thiểu trong cửa sổ nền để tính change_pct.
#}
{% macro hot_score_model(recent_days, baseline_days, min_baseline) %}
{% set w_recent = "rows between " ~ (recent_days - 1) ~ " preceding and current row" %}
{% set w_base = "rows between " ~ (recent_days + baseline_days - 1) ~ " preceding and " ~ recent_days ~ " preceding" %}
{% set recent_weeks = recent_days // 7 %}
{% set min_ly_days = (recent_days * 0.7) | round(0, 'ceil') | int %}

-- Mốc là ngày mới nhất mà Wikipedia đã có số liệu cho gần đủ các điểm; ngày đang cập nhật dở (mới có vài điểm) sẽ bị bỏ qua.
with day_coverage as (
    select date, count(*) filter (where wiki_views is not null)::float / count(*) as share
    from {{ ref('fct_place_daily_signals') }}
    group by 1
),

latest as (
    select max(date) as d from day_coverage where share >= {{ var('min_day_coverage') }}
),

-- Số bài báo theo cửa sổ 7 ngày. Mỗi lần chạy neo cửa sổ vào ngày chạy, nên chỉ lấy các cửa sổ cùng nhịp với cửa sổ mới nhất.
anchor as (select max(window_start) as a from {{ source('raw', 'news_volume') }}),

news_metrics as (
    select
        v.place_id,
        sum(v.articles) filter (where (a.a - v.window_start) / 7 < {{ recent_weeks }})                                   as news_recent,
        sum(v.articles) filter (where (a.a - v.window_start) / 7 between {{ recent_weeks }} and {{ recent_weeks + 3 }}) as news_base,
        count(*) filter (where (a.a - v.window_start) / 7 <= {{ recent_weeks + 3 }})                                     as n_windows
    from {{ source('raw', 'news_volume') }} v
    cross join anchor a
    where (a.a - v.window_start) % 7 = 0
    group by 1
),

base as (
    select
        s.place_id, s.date, s.wiki_views,
        avg(s.wiki_views)       over (partition by s.place_id order by s.date {{ w_recent }}) as level_avg,
        avg(s.vi_views)         over (partition by s.place_id order by s.date {{ w_recent }}) as vi_avg,
        avg(s.intl_views)       over (partition by s.place_id order by s.date {{ w_recent }}) as intl_avg,
        avg(s.wiki_views)       over (partition by s.place_id order by s.date {{ w_base }})   as base_avg,
        count(s.wiki_views)     over (partition by s.place_id order by s.date {{ w_base }})   as base_days,
        avg(s.wiki_views_ly)    over (partition by s.place_id order by s.date {{ w_recent }}) as ly_avg,
        avg(s.intl_views_ly)    over (partition by s.place_id order by s.date {{ w_recent }}) as intl_ly_avg,
        count(s.wiki_views_ly)  over (partition by s.place_id order by s.date {{ w_recent }}) as ly_days,
        (s.date = l.d and nm.n_windows = {{ recent_weeks + 4 }})                              as news_ok,
        nm.news_recent, nm.news_base
    from {{ ref('fct_place_daily_signals') }} s
    cross join latest l
    left join news_metrics nm on nm.place_id = s.place_id
),

with_signals as (
    select *,
        case when base_days >= {{ min_baseline }} and base_avg > 0 then level_avg / base_avg - 1 end as change_pct,
        case when ly_days >= {{ min_ly_days }} and ly_avg > 0
              and level_avg / ly_avg between 1.0 / {{ var('yoy_max_ratio') }} and {{ var('yoy_max_ratio') }}
             then ln((level_avg + {{ var('yoy_prior_views') }}) / (ly_avg + {{ var('yoy_prior_views') }})) end as yoy,
        case when ly_days >= {{ min_ly_days }} and ly_avg > 0
              and level_avg / ly_avg between 1.0 / {{ var('yoy_max_ratio') }} and {{ var('yoy_max_ratio') }}
             then level_avg / ly_avg - 1 end as yoy_pct,
        case when ly_days >= {{ min_ly_days }} and intl_ly_avg > 0 and intl_avg + intl_ly_avg >= {{ var('min_intl_views') }}
              and intl_avg / intl_ly_avg between 1.0 / {{ var('yoy_max_ratio') }} and {{ var('yoy_max_ratio') }}
             then ln((intl_avg + {{ var('yoy_prior_views') }}) / (intl_ly_avg + {{ var('yoy_prior_views') }})) end as intl_yoy,
        case when ly_days >= {{ min_ly_days }} and intl_ly_avg > 0 and intl_avg + intl_ly_avg >= {{ var('min_intl_views') }}
              and intl_avg / intl_ly_avg between 1.0 / {{ var('yoy_max_ratio') }} and {{ var('yoy_max_ratio') }}
             then intl_avg / intl_ly_avg - 1 end as intl_yoy_pct,
        case when news_ok
             then ln((news_recent / {{ recent_weeks }}.0 + {{ var('news_prior_articles') }}) / (news_base / 4.0 + {{ var('news_prior_articles') }})) end as news_growth
    from base
    where wiki_views is not null and date <= (select d from latest)  -- bỏ ngày dữ liệu còn dở
),

gated as (
    -- điều kiện xếp hạng: phải có lượng quan tâm ngoài nhóm thấp nhất, vì phần trăm tăng trên nền vài chục lượt xem chỉ là nhiễu
    select *, percent_rank() over (partition by date order by level_avg) as pre_attention
    from with_signals
),

ranked as (
    select *,
        percent_rank() over (partition by date order by level_avg) as attention_pct,
        -- partition thêm theo (cột có null hay không) để xếp hạng phần trăm chỉ trong nhóm có giá trị
        case when yoy is not null then percent_rank() over (partition by date, (yoy is not null) order by yoy) end as yoy_rank,
        case when intl_yoy is not null then percent_rank() over (partition by date, (intl_yoy is not null) order by intl_yoy) end as intl_rank,
        case when news_growth is not null then percent_rank() over (partition by date, (news_growth is not null) order by news_growth) end as news_pct
    from gated
    where pre_attention >= {{ var('min_attention_pct') }}
),

scored as (
    select *,
        -- trọng số bằng nhau nên điểm chỉ là trung bình của các phân vị có mặt
        1 + (yoy_rank is not null)::int + (intl_rank is not null)::int + (news_pct is not null)::int as n_signals,
        attention_pct + coalesce(yoy_rank, 0) + coalesce(intl_rank, 0) + coalesce(news_pct, 0) as pct_sum
    from ranked
)

select
    place_id, date, wiki_views,
    round(level_avg::numeric, 1)  as level,
    round(vi_avg::numeric, 1)     as vi_level,
    round(intl_avg::numeric, 1)   as intl_level,
    round(base_avg::numeric, 1)   as base,
    round(ly_avg::numeric, 1)     as ly_level,
    round(change_pct::numeric, 3) as change_pct,
    round(yoy::numeric, 3)        as yoy,
    round(yoy_pct::numeric, 3)    as yoy_pct,
    round(intl_yoy::numeric, 3)   as intl_yoy,
    round(intl_yoy_pct::numeric, 3) as intl_yoy_pct,
    round(intl_ly_avg::numeric, 1)  as intl_ly_level,
    case when news_ok then news_recent end as news_recent,
    case when news_ok then news_base end   as news_base,
    round(news_growth::numeric, 3) as news_growth,
    round(attention_pct::numeric, 3) as p_attention,
    round(yoy_rank::numeric, 3)      as p_yoy,
    round(intl_rank::numeric, 3)     as p_intl,
    round(news_pct::numeric, 3)      as p_news,
    round((100 * pct_sum / n_signals)::numeric, 1) as hot_score,
    n_signals
from scored
where n_signals >= {{ var('min_signals') }}
{% endmacro %}
