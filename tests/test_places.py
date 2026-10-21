import pytest

from tourism.config import load_places, load_provinces
from tourism.places import PlaceMatcher, normalize


@pytest.fixture(scope="module")
def matcher():
    return PlaceMatcher(load_places())


def ids(mentions):
    return {m.place_id for m in mentions}


def test_normalize_strips_diacritics_and_d_bar():
    assert normalize("Đà Lạt – sương mù!") == " da lat suong mu "


def test_match_with_and_without_diacritics(matcher):
    assert ids(matcher.find("Du lịch Đà Lạt cuối tuần")) == {"ho-xuan-huong"}
    assert ids(matcher.find("Kinh nghiem di Da Lat")) == {"ho-xuan-huong"}


def test_alias_matches(matcher):
    assert ids(matcher.find("Check-in Sapa mùa săn mây")) == {"sa-pa"}
    assert ids(matcher.find("Chinh phục Fansipan")) == {"fansipan"}


def test_in_title_flag_distinguishes_title_from_summary(matcher):
    [m] = matcher.find("Lễ hội mới", "Du khách đổ về Phú Quốc dịp này")
    assert m.place_id == "phu-quoc" and m.in_title is False
    [m] = matcher.find("Phú Quốc đón khách", "")
    assert m.in_title is True


def test_multiple_places_in_one_article(matcher):
    assert ids(matcher.find("Vịnh Hạ Long - Tràng An - Sa Pa trong 5 ngày")) == {"vinh-ha-long", "trang-an", "sa-pa"}


def test_no_match_inside_longer_word(matcher):
    assert ids(matcher.find("Giá vé máy bay giảm mạnh")) == set()
    assert ids(matcher.find("Thị trường hotel phục hồi")) == set()


def test_province_name_alone_is_not_an_attraction(matcher):
    # Tên tỉnh/thành đứng một mình không được tính cho điểm tham quan nào (tránh quay lại mức xếp hạng theo tỉnh).
    assert ids(matcher.find("Đà Nẵng đón khách quốc tế", "Thành phố Đà Nẵng tăng chuyến bay")) == set()


def test_every_place_has_required_fields():
    places = load_places()
    assert len({p.place_id for p in places}) == len(places)
    for p in places:
        assert 8 <= p.lat <= 24 and 102 <= p.lon <= 110, p.place_id
        assert p.aliases, p.place_id
        assert p.wiki_title, p.place_id


def test_hierarchy_is_consistent():
    provinces = {p.province_id: p for p in load_provinces()}
    assert len(provinces) == len(load_provinces())
    assert {p.region for p in provinces.values()} == {"Miền Bắc", "Miền Trung", "Miền Nam"}
    for place in load_places():
        assert place.province_id in provinces, f"{place.place_id}: tỉnh {place.province_id} không tồn tại"
    # mỗi tỉnh khai báo phải có ít nhất một điểm tham quan
    used = {p.province_id for p in load_places()}
    assert used == set(provinces), f"tỉnh không có điểm nào: {set(provinces) - used}"
