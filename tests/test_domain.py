"""Offline tests — parse the real captured br.de RSS feeds and one
real article page (a wissen NewsArticle with an empty JSON-LD
articleBody and an embedded VideoObject, so the body comes from the
server-rendered <article> paragraphs), no network."""
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from br_mcp import domain as dom
from br_mcp import http as http_mod

FIX = pathlib.Path(__file__).resolve().parent / "fixtures"


def _read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


class TestHeadlinesFeed:
    def test_ticker_shape(self):
        parsed = dom.parse_rss(_read("headlines.xml"))
        assert parsed["feed_title"] == "Die Nachrichten des Bayerischen Rundfunks"
        assert parsed["count"] == 7
        assert len(parsed["items"]) == 7

    def test_ticker_items_are_short_news(self):
        parsed = dom.parse_rss(_read("headlines.xml"))
        first = parsed["items"][0]
        assert first["title"] == "Bundesrat beschließt Frühstartrente"
        # Ticker items all link to the shared index page with an anchor.
        assert first["link"] == (
            "https://www.br.de/nachrichten/meldungen/index.html#n1"
        )
        # The description IS the whole short news text.
        assert first["description"].startswith(
            "Frühstart-Rente kann in Kraft treten"
        )
        assert len(first["description"]) > 200
        assert first["published"] == "2026-11-20T10:13:06+00:00"
        assert all(i["title"] and i["description"] for i in parsed["items"])

    def test_ticker_items_have_no_category_or_image(self):
        parsed = dom.parse_rss(_read("headlines.xml"))
        assert all(i["category"] is None for i in parsed["items"])
        assert all(i["image_url"] is None for i in parsed["items"])


class TestCategoryFeed:
    def test_wissen_shape(self):
        parsed = dom.parse_rss(_read("category-wissen.xml"))
        assert parsed["count"] == 50
        assert len(parsed["items"]) == 50

    def test_wissen_first_item(self):
        parsed = dom.parse_rss(_read("category-wissen.xml"))
        first = parsed["items"][0]
        assert first["title"] == (
            "Herbstlaub: Wer muss räumen und wer haftet bei Unfällen?"
        )
        assert first["link"] == (
            "https://www.br.de/nachrichten/wissen/"
            "was-gilt-unfaelle-durch-herbstlaub-auf-laub-ausgerutscht-haftung,UQDgunl"
        )
        assert first["category"] == "Wissen"
        assert first["image_url"].startswith("https://img.br.de/")
        assert first["published"] == "2026-11-19T12:51:36+00:00"

    def test_all_wissen_items_carry_category_and_image(self):
        parsed = dom.parse_rss(_read("category-wissen.xml"))
        assert all(i["category"] == "Wissen" for i in parsed["items"])
        assert all(
            (i["image_url"] or "").startswith("https://img.br.de/")
            for i in parsed["items"]
        )
        assert all(i["link"].startswith("https://www.br.de/nachrichten/wissen/")
                    for i in parsed["items"])


class TestRadioFeed:
    def test_bayern1_shape(self):
        parsed = dom.parse_rdf(_read("radio-bayern1.xml"))
        assert parsed["count"] == 80
        assert len(parsed["items"]) == 80

    def test_bayern1_first_item(self):
        parsed = dom.parse_rdf(_read("radio-bayern1.xml"))
        first = parsed["items"][0]
        assert first["title"].startswith("Nüchtern zum Arzt")
        assert first["link"].endswith(".html")
        assert first["link"].startswith("https://www.br.de/radio/bayern1/")
        # dc:date parses despite the feed's typo'd dc namespace
        # (dc/elments/1.1/ instead of dc/elements/1.1/).
        assert first["published"] == "2026-02-11T10:39:00+00:00"
        assert first["description"]

    def test_bayern1_all_items_have_links_and_dates(self):
        parsed = dom.parse_rdf(_read("radio-bayern1.xml"))
        assert all(i["link"] for i in parsed["items"])
        assert all(i["published"] for i in parsed["items"])
        # 13 of 80 items link off-site (ARD Audiothek episodes and
        # Instagram reels) — the feed mixes them in; they are returned
        # as-is and br_get_article never fetches them.
        offsite = [i for i in parsed["items"]
                   if not i["link"].startswith("https://www.br.de/")]
        assert len(offsite) == 13
        assert all("ardsounds.de" in i["link"]
                   or "ardaudiothek.de" in i["link"]
                   or "instagram.com" in i["link"]
                   for i in offsite)


class TestTrafficFeed:
    def test_traffic_shape(self):
        parsed = dom.parse_rss(_read("traffic.xml"))
        assert parsed["feed_title"] == "Verkehrsmeldungen des Bayerischen Rundfunks"
        assert parsed["count"] == 14

    def test_traffic_first_item_is_self_contained(self):
        parsed = dom.parse_rss(_read("traffic.xml"))
        first = parsed["items"][0]
        assert first["description"] == (
            "A81 Richtung Heilbronn zwischen Dreieck Würzburg-West und "
            "Gerchsheim liegt ein Styropor-Paket (11:04)"
        )
        # Traffic items link to the legacy br-online.de host.
        assert first["link"].startswith("http://www.br-online.de/")


class TestArticle:
    def test_wissen_article(self):
        art = dom.parse_article(_read("article-wissen.html"))
        assert art["kind"] == "article"
        assert art["title"] == (
            "Unfälle durch Herbstlaub: Auf Laub ausgerutscht - wer haftet?"
        )
        assert art["author"] == "Marlene Riederer"
        assert art["published"] == "2024-10-10T10:00:04.710447+00:00"
        assert art["word_count"] == 684
        assert art["paywalled"] is False
        assert art["teaser_only"] is False
        assert art["video_url"] is None

    def test_article_body_is_ssr_not_video(self):
        # The page carries a VideoObject block BEFORE its NewsArticle
        # block, and the NewsArticle articleBody is empty: the body
        # must still come from the <article> paragraphs, not from the
        # video description.
        art = dom.parse_article(_read("article-wissen.html"))
        assert art["body"].startswith(
            "Der Herbst bringt bunte Blätter, kühlere Temperaturen"
        )
        assert "rutschiges Laub" in art["body"]
        assert "Über dieses Thema berichtet" not in art["body"]
        # The teaser paragraph must not repeat at the top of the body.
        assert not art["body"].startswith(art["description"][:40])

    def test_article_description_is_the_teaser(self):
        art = dom.parse_article(_read("article-wissen.html"))
        assert art["description"].startswith(
            "Im Herbst fällt das Laub von den Bäumen"
        )


class TestValidators:
    def test_limit(self):
        assert dom.validate_limit(1) == 1
        assert dom.validate_limit(150) == 150
        with pytest.raises(ValueError):
            dom.validate_limit(0)
        with pytest.raises(ValueError):
            dom.validate_limit(151)

    def test_category(self):
        assert dom.validate_category("Wissen") == "wissen"
        assert dom.validate_category(" BAYERN ") == "bayern"
        with pytest.raises(ValueError):
            dom.validate_category("deutschland")  # 404 on the live site

    def test_station(self):
        assert dom.validate_station("Bayern2") == "bayern2"
        with pytest.raises(ValueError):
            dom.validate_station("bayern3")  # no such feed


class TestSearchAndDedupe:
    def test_search_items(self):
        parsed = dom.parse_rss(_read("category-wissen.xml"))
        found = dom.search_items(parsed["items"], "Herbstlaub")
        # Two Herbstlaub stories in the feed (19 Nov + 7 Nov 2026).
        assert len(found) == 2
        assert all("herbstlaub" in i["title"].casefold() for i in found)
        assert dom.search_items(parsed["items"], "herbstlaub") == found
        with pytest.raises(ValueError):
            dom.search_items(parsed["items"], "   ")

    def test_dedupe_sort(self):
        parsed = dom.parse_rss(_read("category-wissen.xml"))
        doubled = parsed["items"] + parsed["items"][:5]
        out = dom.dedupe_sort(doubled)
        assert len(out) == 50
        pubs = [i["published"] for i in out]
        assert pubs == sorted(pubs, reverse=True)


class TestFeedGuards:
    def test_parse_rss_rejects_garbage(self):
        with pytest.raises(ValueError):
            dom.parse_rss("<html><body>not rss</body></html>")

    def test_parse_rdf_rejects_garbage(self):
        with pytest.raises(ValueError):
            dom.parse_rdf("<html><body>not rss</body></html>")

    def test_fetch_article_refuses_ticker_links(self):
        with pytest.raises(http_mod.BrError):
            http_mod.fetch_article(
                "https://www.br.de/nachrichten/meldungen/index.html#n1"
            )
        with pytest.raises(http_mod.BrError):
            http_mod.fetch_article(
                "https://www.br.de/nachrichten/meldungen/index.html"
            )

    def test_fetch_article_refuses_other_hosts(self):
        with pytest.raises(http_mod.BrError):
            http_mod.fetch_article(
                "http://www.br-online.de/aktuell/verkehr/verkehr-verkehrsmeldungen-"
                "staumeldungen-ID119730167093.xml"
            )

    def test_fetch_feed_refuses_non_feed_urls(self):
        with pytest.raises(http_mod.BrError):
            http_mod.fetch_feed("https://www.br.de/nachrichten/wissen/")


class TestServerEnvelope:
    def test_tools_return_json_envelope(self):
        # Offline: the tools hit the network, so only the error path
        # is exercised here — but the envelope shape is the same.
        from br_mcp import server as srv

        out = json.loads(srv.br_news_by_category("deutschland"))
        assert "error" in out
        assert out["source"] == "www.br.de"
        assert "fetched_at" in out
