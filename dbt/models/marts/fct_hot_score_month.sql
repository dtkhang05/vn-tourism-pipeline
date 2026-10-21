-- Điểm nóng theo tháng: mức quan tâm 30 ngày, xu hướng so với 30 ngày trước đó. Cần ~60 ngày lịch sử Wikipedia.
{{ hot_score_model(30, 30, var('min_baseline_days_month')) }}
