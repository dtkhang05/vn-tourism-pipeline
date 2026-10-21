from datetime import date

from tourism.ingest.news_volume import count_articles


class FakeResponse:
    status_code = 200

    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        pass


class FakeHttp:
    def __init__(self, text: str):
        self.text = text
        self.last_query = None

    def get(self, url, params, timeout):
        self.last_query = params["q"]
        return FakeResponse(self.text)


def feed(*pub_dates: str) -> str:
    items = "".join(f"<item><title>x</title><pubDate>{d}</pubDate></item>" for d in pub_dates)
    return f"<rss><channel><title>Google Tin tức</title>{items}</channel></rss>"


def test_count_articles_only_counts_the_window():
    # Google tính cả ngày "before", nên bài ngày 13/10 (ngoài cửa sổ 6 đến 12/10) phải bị loại.
    http = FakeHttp(feed("Tue, 06 Oct 2026 07:00:00 GMT", "Sun, 11 Oct 2026 07:00:00 GMT", "Tue, 13 Oct 2026 07:00:00 GMT", "Mon, 05 Oct 2026 07:00:00 GMT"))
    assert count_articles(http, "Hội An", date(2026, 10, 6)) == 2


def test_count_articles_builds_a_dated_query():
    http = FakeHttp(feed())
    assert count_articles(http, "Sa Pa", date(2026, 10, 6)) == 0
    assert http.last_query == '"Sa Pa" du lịch after:2026-10-06 before:2026-10-13'
