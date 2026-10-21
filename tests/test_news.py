from datetime import UTC, datetime

from tourism.ingest import news

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>t</title>
<item>
  <title>Du lịch &lt;b&gt;Đà Lạt&lt;/b&gt; mùa mưa</title>
  <link>https://example.com/a</link>
  <description><![CDATA[<p>Sương mù &amp; hoa dã quỳ</p>]]></description>
  <pubDate>Tue, 20 Oct 2026 02:30:00 +0000</pubDate>
</item>
<item><title>Không có link</title></item>
</channel></rss>"""


class FakeResponse:
    content = RSS.encode("utf-8")

    def raise_for_status(self):
        pass


class FakeSession:
    def get(self, url, timeout):
        return FakeResponse()


def test_fetch_feed_parses_and_cleans(monkeypatch):
    monkeypatch.setattr(news, "session", lambda: FakeSession())
    [row] = news.fetch_feed("example", "https://example.com/rss")
    url, source, title, summary, _ = row
    assert (url, source) == ("https://example.com/a", "example")
    assert title == "Du lịch Đà Lạt mùa mưa"
    assert summary == "Sương mù & hoa dã quỳ"


def test_published_at_is_utc_regardless_of_machine_timezone(monkeypatch):
    monkeypatch.setenv("TZ", "Asia/Ho_Chi_Minh")
    monkeypatch.setattr(news, "session", lambda: FakeSession())
    [row] = news.fetch_feed("example", "https://example.com/rss")
    assert row[4] == datetime(2026, 10, 20, 2, 30, tzinfo=UTC)
