import html
import json
import os
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st
from queries import QUERIES
from sqlalchemy import create_engine

TOP_N = 5  # số điểm trong phần áp phích
LIST_N = 15  # số dòng của danh sách rút gọn trước khi bấm "xem thêm"
WEEKEND_FLAG = 3.0  # lượt xem ngày thường gấp từng này lần cuối tuần thì gắn nhãn cảnh báo (trung vị của các điểm là ~1,2)
REGIONS = ["Tất cả", "Miền Bắc", "Miền Trung", "Miền Nam"]
REGION_CLASS = {"Miền Bắc": "bac", "Miền Trung": "trung", "Miền Nam": "nam"}
REGION_RGB = {"Miền Bắc": [110, 168, 255], "Miền Trung": [45, 212, 191], "Miền Nam": [183, 155, 255]}
PERIODS = {
    "Tuần này": {
        "rank": "hot_rank", "score": "hot_score", "level": "level_7d", "vi": "vi_7d", "intl": "intl_7d", "ly": "ly_7d", "change": "change_pct",
        "yoy": "yoy_pct", "iyoy": "intl_yoy_pct", "news": "news_7d", "news_base": "news_base_7d", "has": "has_signal", "n": "n_signals",
        "pa": "p_attention", "py": "p_yoy", "pi": "p_intl", "pn": "p_news",
        "label": "tuần", "span": "7 ngày", "weeks": 1, "versus": "4 tuần trước",
    },
    "Tháng này": {
        "rank": "hot_rank_30d", "score": "hot_score_30d", "level": "level_30d", "vi": "vi_30d", "intl": "intl_30d", "ly": "ly_30d", "change": "change_pct_30d",
        "yoy": "yoy_pct_30d", "iyoy": "intl_yoy_pct_30d", "news": "news_30d", "news_base": "news_base_30d", "has": "has_signal_30d", "n": "n_signals_30d",
        "pa": "p_attention_30d", "py": "p_yoy_30d", "pi": "p_intl_30d", "pn": "p_news_30d",
        "label": "tháng", "span": "30 ngày", "weeks": 4, "versus": "30 ngày trước đó",
    },
}
PROVINCE_MODE = "Tỉnh thành"
PROVINCE_COLS = {
    "Tuần này": {"rank": "hot_rank", "score": "province_score", "avg": "avg_hot_score", "max": "max_hot_score", "n": "n_places_scored", "top": "top_place", "top_id": "top_place_id"},
    "Tháng này": {"rank": "hot_rank_30d", "score": "province_score_30d", "avg": "avg_hot_score_30d", "max": "max_hot_score_30d", "n": "n_places_scored_30d",
                  "top": "top_place_30d", "top_id": "top_place_id_30d"},
}

# ------------------------------------------------------------------ biểu tượng thời tiết (SVG tự vẽ, không dùng ảnh ngoài)
SUN_ICON = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="5" fill="#FFC93C"/><g stroke="#FFC93C" stroke-width="2" stroke-linecap="round">'
    '<path d="M12 1v3M12 20v3M1 12h3M20 12h3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/></g></svg>'
)
RAIN_ICON = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 15a4 4 0 0 1 .6-7.9A5.5 5.5 0 0 1 18 9a3.5 3.5 0 0 1-.5 7H7Z" fill="#9DB6DB"/>'
    '<g stroke="#2F6BFF" stroke-width="2" stroke-linecap="round"><path d="M8 19l-1 3M12 19l-1 3M16 19l-1 3"/></g></svg>'
)


st.set_page_config(page_title="Điểm du lịch hot ở Việt Nam", page_icon="🌴", layout="wide")
st.markdown(f"<style>{(Path(__file__).parent / 'style.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


@st.cache_resource
def engine():
    url = "postgresql+psycopg2://{u}:{p}@{h}:{port}/{db}".format(
        u=os.getenv("PGUSER", "tourism"),
        p=os.getenv("PGPASSWORD", "tourism"),
        h=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        db=os.getenv("PGDATABASE", "tourism"),
    )
    return create_engine(url)


SNAPSHOT_DIR = Path(__file__).parent / "snapshot"


@st.cache_data(ttl=300)
def query(sql: str, name: str) -> pd.DataFrame:
    """Đọc từ Postgres; nếu không kết nối được (bản đưa lên web không có CSDL) thì đọc ảnh chụp dữ liệu app/snapshot/<name>.parquet
    do scripts/export_snapshot.py tạo. Đặt DASHBOARD_SNAPSHOT=1 để luôn dùng ảnh chụp."""
    snap = SNAPSHOT_DIR / f"{name}.parquet"
    if os.getenv("DASHBOARD_SNAPSHOT") != "1":
        try:
            return pd.read_sql(sql, engine())
        except Exception:
            if not snap.exists():
                raise
    return pd.read_parquet(snap)


@st.cache_data
def _read_images(path: str, mtime: float) -> dict[str, dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))  # mtime nằm trong khóa bộ nhớ đệm để đổi file là đọc lại


def _find_json(name: str) -> Path | None:
    for p in (Path(__file__).parent / name, Path(__file__).resolve().parents[1] / "config" / name):
        if p.exists():
            return p
    return None


def load_images() -> dict[str, dict]:
    """Ảnh đại diện từ Wikimedia Commons (scripts/fetch_place_images.py và config/province_images.json). Thiếu file thì dùng khung màu.
    Ảnh riêng của tỉnh có khóa "prov:<tên tỉnh>"; dùng cho tỉnh chỉ có một điểm, để thẻ tỉnh không lặp ảnh thẻ điểm."""
    out: dict[str, dict] = {}
    for name, prefix in (("place_images.json", ""), ("province_images.json", "prov:")):
        p = _find_json(name)
        if p:
            out.update({prefix + k: v for k, v in _read_images(str(p), p.stat().st_mtime).items()})
    return out


IMAGES = load_images()


# ------------------------------------------------------------------ định dạng
def esc(x) -> str:
    return html.escape(str(x))


def num(x: float, digits: int = 1) -> str:
    return f"{x:.{digits}f}".replace(".", ",")


def thousands(x: float) -> str:
    return f"{round(x):,}".replace(",", ".")


def region_chip(region: str) -> str:
    return f'<span class="chip {REGION_CLASS.get(region, "")}">{esc(region)}</span>'


def trend_html(change) -> str:
    """Luôn kèm ký hiệu và dấu, không chỉ dựa vào màu."""
    if change is None or pd.isna(change):
        return '<span class="tr flat">thiếu dữ liệu</span>'
    pct = change * 100
    if pct >= 5:
        return f'<span class="tr up">▲ +{thousands(pct)}%</span>'
    if pct <= -5:
        return f'<span class="tr down">▼ {thousands(pct)}%</span>'
    return '<span class="tr flat">≈ ổn định</span>'


PROVINCE_PHOTO: dict[str, str] = {}  # tỉnh -> mã điểm có ảnh dùng cho thẻ tỉnh; điền khi vào chế độ Tỉnh thành


def province_photo_id(province: str, top_id: str) -> str:
    """Thẻ tỉnh dùng ảnh khác với thẻ điểm nổi nhất của tỉnh đó: ảnh điểm thứ hai của tỉnh, hoặc ảnh riêng của tỉnh nếu tỉnh chỉ có một điểm."""
    if province in PROVINCE_PHOTO:
        return PROVINCE_PHOTO[province]
    return f"prov:{province}" if f"prov:{province}" in IMAGES else top_id


def photo(place_id: str, region: str) -> tuple[str, str]:
    """(lớp CSS, thẻ <img>) cho ảnh thẻ; không có ảnh thì dùng khung màu theo miền.
    Dùng <img> thay cho ảnh nền để trình duyệt tải lười và chọn bản 640px trên điện thoại."""
    img = IMAGES.get(place_id)
    if img:
        url = esc(img["url"])
        small = url.replace("/960px-", "/500px-")
        return "", (
            f'<img class="im" src="{url}" srcset="{small} 500w, {url} 960w" sizes="(max-width: 800px) 40vw, 960px" '
            'loading="lazy" decoding="async" alt="">'
        )
    return f"nophoto m-{REGION_CLASS.get(region, 'bac')}", ""


def flag_html(r: dict) -> str:
    ratio = r.get("weekday_weekend_ratio")
    if ratio is None or pd.isna(ratio) or ratio < WEEKEND_FLAG:
        return ""
    tip = f"Lượt xem ngày thường gấp {num(ratio)} lần cuối tuần, có thể là tra cứu học tập hoặc công việc hơn là quan tâm du lịch."
    return f'<div class="flag" title="{esc(tip)}">Lượt xem thấp hẳn vào cuối tuần</div>'


DRY_MAX_MM = 10  # tổng lượng mưa dự báo 3 ngày (mm) tối đa để gọi là "ít mưa" (khoảng 3 mm mỗi ngày)


def weather_html(wx: dict | None) -> str:
    """Nhãn thời tiết kèm tổng lượng mưa 3 ngày; ngưỡng "ít mưa" dùng chung với bộ lọc gợi ý để nhãn và lựa chọn không mâu thuẫn."""
    if not wx:
        return ""
    rain = wx["rain"]
    if rain < 3:
        icon, text = SUN_ICON, "Hầu như không mưa"
    elif rain < DRY_MAX_MM:
        icon, text = SUN_ICON, "Ít mưa"
    elif rain < 20:
        icon, text = RAIN_ICON, "Có mưa rào"
    else:
        icon, text = RAIN_ICON, "Mưa nhiều"
    return f'<div class="wx">{icon}<span>{text} ({round(rain)} mm), {round(wx["temp"])}°C</span></div>'


def credit_short(place_id: str) -> str:
    img = IMAGES.get(place_id)
    if not img:
        return ""
    who = img.get("artist") or "Wikimedia Commons"
    if "//" in who or who.startswith("["):  # trường tác giả của Commons đôi khi là mã liên kết thô
        who = "Wikimedia Commons"
    return f'<div class="credit">Ảnh: {esc(who[:34])}, {esc(img.get("license", ""))}</div>'


def intl_share(r: dict, p: dict) -> float | None:
    level, intl = r[p["level"]], r[p["intl"]]
    if pd.isna(level) or pd.isna(intl) or level <= 0:
        return None
    return float(intl) / float(level)


def intl_chip(r: dict, p: dict) -> str:
    s = intl_share(r, p)
    if s is None:
        return ""
    tip = f"{round(s * 100)}% lượt xem Wikipedia đến từ bài tiếng Anh, Hàn, Trung, Nhật; còn lại từ bài tiếng Việt."
    return f'<span class="chip intl" title="{esc(tip)}">Quốc tế {round(s * 100)}%</span>'


# Bốn tín hiệu cấu thành điểm: (nhãn, khóa phân vị, ý nghĩa). Mỗi hàng: nhãn, thanh phân vị, giá trị thật.
SIGNALS = (("Quan tâm", "pa", "mức quan tâm hiện tại"), ("Cùng kỳ", "py", "tăng so với cùng kỳ năm trước"),
           ("Quốc tế", "pi", "khách quốc tế tăng so với cùng kỳ năm trước"), ("Báo chí", "pn", "tăng độ phủ báo chí"))


def signal_rows(r: dict, p: dict) -> str:
    """Bốn hàng căn đều nhau: nhãn | thanh phân vị so với cả nước | giá trị thật (không cho xuống dòng)."""
    values = {
        "pa": f'{thousands(r[p["level"]])}/ngày',
        "py": trend_html(r[p["yoy"]]),
        "pi": trend_html(r[p["iyoy"]]),
        "pn": "thiếu dữ liệu" if pd.isna(r[p["news_base"]]) else f'{int(r[p["news"]])} bài',
    }
    out = ""
    for label, k, meaning in SIGNALS:
        v = r[p[k]]
        if pd.isna(v):
            bar = '<span class="tk na"></span>'
            tip = f"{label}: chưa đủ dữ liệu"
        else:
            bar = f'<span class="tk"><i style="width:{max(4, round(v * 100))}%"></i></span>'
            tip = f"{label} ({meaning}): cao hơn {round(v * 100)}% số điểm còn lại"
        out += f'<div class="rw" title="{esc(tip)}"><span class="lb">{label}</span>{bar}<span class="vl">{values[k]}</span></div>'
    return f'<div class="rows">{out}</div>'


def poster(r: dict, p: dict) -> str:
    """Thẻ top 5, tỉ lệ 16:9: hạng và tên ở góc trên trái, tỉnh ở góc dưới trái, miền, quốc tế và so với cùng kỳ ở góc dưới phải; bốn tín hiệu trong khung kính nhỏ phía trên."""
    cls, img = photo(r["place_id"], r["region"])
    return (
        f'<article class="pc"><div class="ph {cls}">{img}<span class="rk">{int(r[p["rank"]])}</span><b class="nm">{esc(r["name"])}</b>'
        f'<span class="pt">{num(r[p["score"]])}<small>điểm</small></span><span class="pv">{esc(r["province"])}</span>{credit_short(r["place_id"])}'
        f'<div class="r">{region_chip(r["region"])}{intl_chip(r, p)}<span class="tr-wrap">{trend_html(r[p["yoy"]])}</span></div></div>'
        f'<div class="bd">{signal_rows(r, p)}{flag_html(r)}</div></article>'
    )


def list_row(r: dict, p: dict) -> str:
    """Thẻ lưới tỉ lệ 16:9, không khung: hạng và tên ở góc trên trái, tỉnh ở góc dưới trái, miền, quốc tế và so với cùng kỳ ở góc dưới phải."""
    cls, img = photo(r["place_id"], r["region"])
    return (
        f'<article class="gc"><div class="ph {cls}">{img}</div>'
        f'<span class="rk">{int(r[p["rank"]])}</span><b class="nm">{esc(r["name"])}</b><span class="pt">{num(r[p["score"]])}</span>'
        f'<span class="pv">{esc(r["province"])}</span>'
        f'<div class="r">{region_chip(r["region"])}{intl_chip(r, p)}<span class="tr-wrap">{trend_html(r[p["yoy"]])}</span></div></article>'
    )


# --- tỉnh, thành
def province_poster(r: dict, q: dict) -> str:
    place_id = province_photo_id(r["province"], r[q["top_id"]])
    cls, img = photo(place_id, r["region"])
    return (
        f'<article class="pc"><div class="ph {cls}">{img}<span class="rk">{int(r[q["rank"]])}</span><b class="nm">{esc(r["province"])}</b>'
        f'<span class="pt">{num(r[q["score"]])}<small>điểm</small></span><span class="pv">Nổi nhất: {esc(r[q["top"]])}</span>{credit_short(place_id)}'
        f'<div class="r">{region_chip(r["region"])}<span class="tr-wrap">{int(r[q["n"]])} điểm xếp hạng</span></div></div>'
        f'<div class="bd"><div class="rows">'
        f'<div class="rw"><span class="lb">Cao nhất</span><span class="tk"><i style="width:{max(4, r[q["max"]]):.0f}%"></i></span><span class="vl">{num(r[q["max"]])}</span></div>'
        f'<div class="rw"><span class="lb">Trung bình</span><span class="tk"><i style="width:{max(4, r[q["avg"]]):.0f}%"></i></span><span class="vl">{num(r[q["avg"]])}</span></div>'
        f"</div></div></article>"
    )


def province_row(r: dict, q: dict) -> str:
    place_id = province_photo_id(r["province"], r[q["top_id"]])
    cls, img = photo(place_id, r["region"])
    return (
        f'<article class="gc"><div class="ph {cls}">{img}</div>'
        f'<span class="rk">{int(r[q["rank"]])}</span><b class="nm">{esc(r["province"])}</b><span class="pt">{num(r[q["score"]])}</span>'
        f'<span class="pv">Nổi nhất: {esc(r[q["top"]])}</span>'
        f'<div class="r">{region_chip(r["region"])}<span class="tr-wrap">{int(r[q["n"]])} điểm</span></div></article>'
    )


# ------------------------------------------------------------------ dữ liệu
places = query(QUERIES["places"], "places")
provinces = query(QUERIES["provinces"], "provinces")
weather = query(QUERIES["weather"], "weather")
WX = {r["place_id"]: {"temp": float(r["temp"]), "rain": float(r["rain"])} for r in weather.to_dict("records") if pd.notna(r["temp"])}

if not places["has_signal"].any():
    st.warning("Chưa có dữ liệu để xếp hạng. Chạy pipeline thu thập và dbt trước (xem README).")
    st.stop()
as_of = pd.to_datetime(places["as_of_date"].iloc[0]).strftime("%d/%m/%Y")

# ------------------------------------------------------------------ tiêu đề và công tắc
st.markdown(
    f'<section class="hero"><h1>Việt Nam đang hot ở đâu?</h1>'
    f"<ul class=\"points\"><li>Xếp hạng từ lượt xem Wikipedia bằng năm ngôn ngữ và độ phủ báo chí</li>"
    f"<li>Mỗi điểm được so với chính nó cùng kỳ năm trước</li>"
    f"<li>Nơi chỉ đông vì đang vào mùa sẽ không tự động đứng đầu</li></ul>"
    f'<div class="facts"><span>{len(places)} điểm tham quan</span><span>{places["province"].nunique()} tỉnh thành</span><span>Số liệu đến {as_of}</span></div></section>',
    unsafe_allow_html=True,
)
MODES = [*PERIODS, PROVINCE_MODE]
mode = st.segmented_control("Xem theo", MODES, default="Tuần này", key="period", label_visibility="collapsed") or "Tuần này"
is_province = mode == PROVINCE_MODE
if is_province:
    st.markdown("**Xếp hạng tỉnh, thành theo**")
    sub = st.segmented_control("Kỳ", list(PERIODS), default="Tuần này", key="pperiod", label_visibility="collapsed") or "Tuần này"
else:
    sub = mode
p = PERIODS[sub]
ranked = places[places[p["has"]]].sort_values(p["rank"])
q = PROVINCE_COLS[sub]
prov_ranked = provinces[provinces[q["rank"]].notna()].sort_values(q["rank"])

# Ảnh thẻ tỉnh: lấy điểm có ảnh đứng thứ hai trong tỉnh (theo kỳ đang xem) để khác với ảnh của điểm nổi nhất.
if is_province:
    by_score = places[places[p["has"]]].sort_values(p["score"], ascending=False)
    for _, r_ in prov_ranked.iterrows():
        others = [pid for pid in by_score.loc[by_score["province"] == r_["province"], "place_id"] if pid != r_[q["top_id"]] and pid in IMAGES]
        if others:
            PROVINCE_PHOTO[r_["province"]] = others[0]

# Nền: ảnh các điểm (hoặc ảnh thẻ của các tỉnh) đang đứng đầu, đổi theo công tắc.
if is_province:
    bg_ids = [province_photo_id(r_["province"], r_[q["top_id"]]) for _, r_ in prov_ranked.head(8).iterrows()]
    bg_ids = [pid for pid in bg_ids if pid in IMAGES][:5]
else:
    bg_ids = [pid for pid in ranked["place_id"].head(8) if pid in IMAGES][:5]
layers = "".join(
    f'<i style="--k:{k};--u:url(\'{esc(IMAGES[pid]["url"])}\');--s:url(\'{esc(IMAGES[pid]["url"].replace("/960px-", "/500px-"))}\')"></i>'
    for k, pid in enumerate(bg_ids)
)
st.markdown(f'<div class="bgshow" aria-hidden="true">{layers}</div>', unsafe_allow_html=True)

# ------------------------------------------------------------------ áp phích top 5
if is_province:
    st.markdown(f'<h2 class="sec">Top {TOP_N} tỉnh, thành {p["label"]} này</h2>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="sec-sub">Điểm của tỉnh là trung bình điểm các điểm đã được xếp hạng, co về trung bình cả nước để tỉnh chỉ có một điểm không đứng đầu chỉ nhờ một con số. '
        f'{p["span"]} đến {as_of}.</p>',
        unsafe_allow_html=True,
    )
    if prov_ranked.empty:
        st.info(f"Chưa đủ dữ liệu để xếp hạng tỉnh theo {p['span']}.")
    else:
        st.markdown(f'<div class="podium">{"".join(province_poster(r, q) for r in prov_ranked.head(TOP_N).to_dict("records"))}</div>', unsafe_allow_html=True)
else:
    st.markdown(f'<h2 class="sec">Top {TOP_N} {p["label"]} này</h2>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="sec-sub">{p["span"]} đến {as_of}.</p>',
        unsafe_allow_html=True,
    )
    if ranked.empty:
        st.info(f"Chưa đủ lịch sử để xếp hạng theo {p['span']}.")
    else:
        st.markdown(f'<div class="podium">{"".join(poster(r, p) for r in ranked.head(TOP_N).to_dict("records"))}</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="howto"><div><h4>Điểm được tính thế nào</h4><ul>'
            "<li>Điểm 0 đến 100, là trung bình của bốn tín hiệu, trọng số bằng nhau.</li>"
            "<li>Mỗi tín hiệu được xếp hạng phần trăm giữa các điểm tham quan.</li>"
            "<li>Quan tâm: lượt xem Wikipedia. Cùng kỳ và Quốc tế: tăng so với năm trước. Báo chí: số bài báo.</li></ul></div>"
            '<div><h4>Đọc kết quả ra sao</h4><ul>'
            "<li>Thanh dài: điểm đó nổi hơn nhiều điểm khác ở tín hiệu ấy. Số bên phải là giá trị thật.</li>"
            "<li>Thanh gạch chéo: chưa đủ dữ liệu.</li>"
            "<li>Nhãn Quốc tế: tỉ lệ lượt xem đến từ bài ngoại ngữ.</li>"
            "<li>Đây là mức quan tâm, không phải số khách thực tế.</li></ul></div></div>",
            unsafe_allow_html=True,
        )

# ------------------------------------------------------------------ hot và thời tiết đẹp (chỉ ở chế độ điểm)
if not is_province:
    st.markdown('<h2 class="sec">Đang hot và ít mưa trong 3 ngày tới</h2>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="sec-sub one">Chọn từ 15 điểm đứng đầu {p["label"]} này những nơi dự báo ít mưa và không quá nóng, để bạn dễ cân nhắc chuyến đi gần.</p>',
        unsafe_allow_html=True,
    )
    dry = [r for r in ranked.head(15).to_dict("records") if r["place_id"] in WX and WX[r["place_id"]]["rain"] < DRY_MAX_MM and WX[r["place_id"]]["temp"] <= 34][:4]
    if dry:
        cards = ""
        for r in dry:
            cls, img = photo(r["place_id"], r["region"])
            cards += (
                f'<article class="gc"><div class="ph {cls}">{img}</div>'
                f'<span class="rk">{int(r[p["rank"]])}</span><b class="nm">{esc(r["name"])}</b><span class="pt">{num(r[p["score"]])}</span>'
                f'<span class="pv">{esc(r["province"])}</span>{weather_html(WX[r["place_id"]])}'
                f'<div class="r">{region_chip(r["region"])}{intl_chip(r, p)}<span class="tr-wrap">{trend_html(r[p["yoy"]])}</span></div></article>'
            )
        st.markdown(f'<div class="grid">{cards}</div>', unsafe_allow_html=True)
    else:
        st.info("Hiện không có điểm nào trong top 15 vừa ít mưa vừa không quá nóng trong 3 ngày tới.")

# ------------------------------------------------------------------ danh sách rút gọn
if is_province:
    st.markdown(f'<h2 class="sec">Các tỉnh, thành còn lại, theo {p["label"]}</h2>', unsafe_allow_html=True)
    rest = prov_ranked.iloc[TOP_N:].to_dict("records")
    if rest:
        st.markdown(f'<div class="grid">{"".join(province_row(r, q) for r in rest)}</div>', unsafe_allow_html=True)
    unlisted = provinces[provinces[q["rank"]].isna()]
    if not unlisted.empty:
        st.caption(f"Chưa xếp hạng vì không có điểm nào đủ điều kiện trong kỳ này: {', '.join(sorted(unlisted['province']))}.")
else:
    st.markdown(f'<h2 class="sec">Danh sách rút gọn, theo {p["label"]}</h2>', unsafe_allow_html=True)
    f1, f2 = st.columns([3, 2])
    with f1:
        st.markdown("**Miền**")
        region = st.segmented_control("Miền", REGIONS, default="Tất cả", key="region", label_visibility="collapsed") or "Tất cả"
    with f2:
        province = st.selectbox("Tỉnh, thành", ["Tất cả tỉnh thành", *sorted(places["province"].unique())], index=0)

    filtered = region != "Tất cả" or province != "Tất cả tỉnh thành"
    view = ranked
    if region != "Tất cả":
        view = view[view["region"] == region]
    if province != "Tất cả tỉnh thành":
        view = view[view["province"] == province]
    if not filtered:
        view = view.iloc[TOP_N:]  # năm điểm đầu đã ở phần áp phích

    if view.empty:
        st.info("Không có điểm nào khớp bộ lọc này.")
    else:
        records = view.to_dict("records")
        show_all = st.session_state.get("show_all_places", False)
        shown = records if show_all else records[:LIST_N]
        st.markdown(f'<div class="grid">{"".join(list_row(r, p) for r in shown)}</div>', unsafe_allow_html=True)
        if len(records) > LIST_N:
            st.button(
                "Thu gọn danh sách" if show_all else f"Xem thêm {len(records) - LIST_N} điểm",
                key="more_places",
                on_click=lambda: st.session_state.update(show_all_places=not show_all),
            )
        st.caption("Số thứ tự là hạng trên cả nước." + (" Chưa lọc thì danh sách bắt đầu từ hạng 6, vì năm điểm đầu đã nằm ở phần trên." if not filtered else ""))

    unranked = places[~places[p["has"]]].sort_values("name")
    if not unranked.empty:
        with st.expander(f"{len(unranked)} điểm chưa được xếp hạng {p['label']} này"):
            st.markdown("Lượng quan tâm thuộc nhóm thấp nhất hoặc chưa đủ tín hiệu, nên mức tăng giảm chỉ là nhiễu: " + ", ".join(esc(n) for n in unranked["name"]) + ".")

# ------------------------------------------------------------------ bản đồ
st.markdown(f'<h2 class="sec">Trên bản đồ, theo {p["label"]}</h2>', unsafe_allow_html=True)
map_df = places.assign(score=places[p["score"]].round(1), radius=places[p["score"]].fillna(0).mul(350).add(8000), color=places["region"].map(REGION_RGB))
st.pydeck_chart(
    pdk.Deck(
        map_provider="carto",
        map_style="dark",
        initial_view_state=pdk.ViewState(latitude=15.9, longitude=106.0, zoom=4.7),
        layers=[pdk.Layer("ScatterplotLayer", map_df, get_position="[lon, lat]", get_radius="radius",
                          radius_min_pixels=5, radius_max_pixels=34, get_fill_color="color", pickable=True)],
        tooltip={"text": "{name}\n{province}\nĐiểm: {score}"},
    ),
    height=440,
)
st.caption("Chấm càng to điểm càng cao. Xanh dương là miền Bắc, xanh ngọc là miền Trung, tím là miền Nam.")

# ------------------------------------------------------------------ cách tính, lưu ý, bằng chứng, nguồn ảnh
st.markdown('<h2 class="sec">Điểm được tính thế nào, và nên đọc kết quả ra sao</h2>', unsafe_allow_html=True)
st.markdown(
    '<div class="note"><b>Mỗi điểm được so với các điểm còn lại trong cùng ngày ở bốn tín hiệu, rồi lấy trung bình với trọng số bằng nhau.</b><br>'
    "Quan tâm: lượt xem Wikipedia của điểm đó ở năm ngôn ngữ (Việt, Anh, Hàn, Trung, Nhật), trung bình 7 ngày hoặc 30 ngày gần nhất.<br>"
    "Cùng kỳ: mức quan tâm so với đúng giai đoạn năm trước (lùi 52 tuần để trùng thứ trong tuần). Nơi chỉ đông vì đang vào mùa không được cộng điểm, "
    "chỉ phần tăng bất thường mới được tính.<br>"
    "Quốc tế: như trên nhưng chỉ tính bài tiếng Anh, Hàn, Trung, Nhật. Người đọc các bản này chủ yếu sắp đi du lịch, không bị lịch học và lịch làm việc ở Việt Nam chi phối.<br>"
    "Báo chí: số bài báo nhắc tên điểm (Google News) trong giai đoạn gần nhất so với bốn tuần trước đó.<br>"
    "Điều kiện xếp hạng: lượng quan tâm không thuộc nhóm thấp nhất và có ít nhất 3 trong 4 tín hiệu; mức tăng hoặc giảm quá 8 lần so với năm trước bị bỏ vì thường do bài Wikipedia bị đổi tên. "
    "Xu hướng ngắn hạn không được tính vì bị lịch học nhiễu (ví dụ Hồ Gươm tăng vọt vào ngày thường khi bài &ldquo;Sự tích Hồ Gươm&rdquo; vào chương trình).<br>"
    "Điểm tỉnh, thành: trung bình điểm các điểm đã được xếp hạng của tỉnh, co về trung bình cả nước (thêm 2 điểm trung bình vào mỗi tỉnh).</div>",
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="warn"><b>Điều cần biết trước khi dựa vào bảng này để chọn chỗ đi.</b> Lượt xem Wikipedia và số bài báo đo mức quan tâm, không phải số người '
    "đến thăm; số liệu khách thật theo địa điểm không được công bố theo ngày. Bài báo có thể nhắc một nơi vì lý do không liên quan du lịch. "
    "Một số nơi nổi tiếng có lượt xem thấp hẳn vào cuối tuần (nhãn cảnh báo trên thẻ), dấu hiệu của tra cứu học tập hoặc công việc. "
    "Google Trends chưa dùng được vì bị Google chặn. Hãy coi đây là gợi ý để tìm hiểu thêm, và kiểm tra giá vé, thời tiết, tình hình thực tế trước khi quyết định.</div>",
    unsafe_allow_html=True,
)
with st.expander("Xem số liệu gốc của từng điểm"):
    ev = ranked[["name", "province", p["rank"], p["score"], p["vi"], p["intl"], p["ly"], p["yoy"], p["news"], p["news_base"], p["pa"], p["py"], p["pi"], p["pn"]]].copy()
    ev[p["yoy"]] = ev[p["yoy"]].mul(100)
    ev[p["news_base"]] = ev[p["news_base"]].div(4).mul(p["weeks"])
    ev.columns = ["Địa điểm", "Tỉnh, thành", "Hạng", "Điểm", "Lượt xem/ngày (Việt)", "Lượt xem/ngày (quốc tế)", "Cùng kỳ năm trước/ngày",
                  "So với cùng kỳ (%)", "Số bài báo", "Số bài báo giai đoạn trước", "Phân vị quan tâm", "Phân vị cùng kỳ", "Phân vị quốc tế", "Phân vị báo chí"]
    st.dataframe(ev, hide_index=True, width="stretch", column_config={
        "Điểm": st.column_config.NumberColumn(format="%.1f"), "So với cùng kỳ (%)": st.column_config.NumberColumn(format="%+.0f%%"),
        "Lượt xem/ngày (Việt)": st.column_config.NumberColumn(format="%.0f"), "Lượt xem/ngày (quốc tế)": st.column_config.NumberColumn(format="%.0f"),
        "Cùng kỳ năm trước/ngày": st.column_config.NumberColumn(format="%.0f"), "Số bài báo giai đoạn trước": st.column_config.NumberColumn(format="%.1f"),
    })
with st.expander("Dữ liệu cập nhật khi nào?"):
    fresh = query(QUERIES["ingest_runs"], "ingest_runs")
    st.dataframe(fresh, hide_index=True, width="stretch")
    st.caption("Trạng thái empty nghĩa là nguồn trả về 0 dòng (ví dụ Google Trends bị chặn), không phải lỗi của hệ thống.")
with st.expander("Nguồn ảnh"):
    names = dict(zip(places["place_id"], places["name"], strict=True))

    def credit_cells(pid: str, i: dict) -> str:
        who = i.get("artist") or ""
        who = "Wikimedia Commons" if "//" in who or who.startswith("[") or not who else who
        return (
            f"<td>{esc(label(pid))}</td>"
            f'<td>{esc(who[:60])}, {esc(i.get("license", ""))}, <a href="{esc(i["page"])}" target="_blank" rel="noopener">Trang ảnh</a></td>'
        )

    def label(pid: str) -> str:
        return pid.removeprefix("prov:") + " (tỉnh)" if pid.startswith("prov:") else names.get(pid, pid)

    items = sorted(IMAGES.items(), key=lambda kv: label(kv[0]))
    rows = ""
    for k in range(0, len(items), 2):
        pair = items[k : k + 2]
        rows += "<tr>" + "".join(credit_cells(pid, i) for pid, i in pair) + ("<td></td><td></td>" if len(pair) == 1 else "") + "</tr>"
    st.markdown(
        '<p class="credits">Ảnh từ Wikimedia Commons. Điểm không có ảnh dùng khung màu thay thế.</p>'
        f'<table class="credits-tb"><thead><tr><th>Tên</th><th>Nguồn</th><th>Tên</th><th>Nguồn</th></tr></thead><tbody>{rows}</tbody></table>',
        unsafe_allow_html=True,
    )
