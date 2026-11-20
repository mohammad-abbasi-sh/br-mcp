"""Live tests — hit the real www.br.de and nachrichtenfeeds.br.de
RSS feeds and article pages. Cautious: few requests.

Run:  pytest tests/test_live.py -v
Skip: pytest -m "not live"  (or set BR_SKIP_LIVE=1)
"""
import json
import os
import pathlib
import sys
import unittest

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from br_mcp import server as srv

pytestmark = pytest.mark.live
SKIP = os.environ.get("BR_SKIP_LIVE") == "1"


@pytest.mark.skipif(SKIP, reason="BR_SKIP_LIVE=1")
class TestLive(unittest.TestCase):
    def test_headlines_live(self):
        out = json.loads(srv.br_headlines(limit=3))
        self.assertNotIn("error", out)
        self.assertGreaterEqual(out["count"], 1)
        self.assertTrue(all(i["title"] and i["description"] for i in out["items"]))
        print(f"\nLIVE headlines: {out['count']} items, first: {out['items'][0]['title']}")

    def test_by_category_live(self):
        out = json.loads(srv.br_news_by_category("bayern", limit=3))
        self.assertNotIn("error", out)
        self.assertEqual(out["category"], "bayern")
        self.assertGreaterEqual(out["count"], 1)
        self.assertTrue(all(i["link"].startswith("https://www.br.de/nachrichten/")
                            for i in out["items"]))
        print(f"\nLIVE bayern: {out['total_results']} items")

    def test_search_live(self):
        out = json.loads(srv.br_search_news("München", limit=3))
        self.assertNotIn("error", out)
        self.assertGreaterEqual(out["count"], 1)
        self.assertTrue(all(
            "münchen" in (i["title"] + i["description"]).casefold()
            for i in out["items"]
        ))
        print(f"\nLIVE search 'München': {out['total_results']} hits")

    def test_get_article_live(self):
        # A category article from the current feed: SSR body expected
        # (BR's JSON-LD articleBody is empty).
        feed = json.loads(srv.br_news_by_category("bayern", limit=10))
        self.assertNotIn("error", feed)
        self.assertGreater(len(feed["items"]), 0)
        out = json.loads(srv.br_get_article(feed["items"][0]["link"]))
        self.assertNotIn("error", out)
        self.assertFalse(out["paywalled"])
        self.assertEqual(out["kind"], "article")
        self.assertGreater(out["word_count"], 100)
        print(f"\nLIVE article: {out['word_count']} words, {out['title'][:60]}")

    def test_radio_live(self):
        out = json.loads(srv.br_radio("bayern1", limit=3))
        self.assertNotIn("error", out)
        self.assertEqual(out["station"], "bayern1")
        self.assertGreaterEqual(out["count"], 1)
        self.assertTrue(all(i["link"].endswith(".html") for i in out["items"]))
        print(f"\nLIVE bayern1: {out['total_results']} items")

    def test_traffic_live(self):
        out = json.loads(srv.br_traffic(limit=3))
        self.assertNotIn("error", out)
        self.assertGreaterEqual(out["count"], 1)
        self.assertTrue(all(i["description"] for i in out["items"]))
        print(f"\nLIVE traffic: {out['total_results']} items")

    def test_health_live(self):
        out = json.loads(srv.br_health())
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["http_status"], 200)


if __name__ == "__main__":
    unittest.main()
