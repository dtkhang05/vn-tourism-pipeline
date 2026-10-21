-- Điểm nóng theo tuần: mức quan tâm 7 ngày, xu hướng so với 28 ngày trước đó. Logic dùng chung ở macros/hot_score.sql.
{{ hot_score_model(7, 28, var('min_baseline_days')) }}
