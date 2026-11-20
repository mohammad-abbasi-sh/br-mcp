"""MCP server: unofficial read-only access to BR (br.de) — the
Bayerischer Rundfunk, Bavaria's public broadcaster and ARD member —
via its official RSS feeds (BR24 news ticker, five category feeds,
Bayern 1 / Bayern 2 radio story feeds, Verkehrsmeldungen) and
article pages (server-rendered <article> text; the JSON-LD
articleBody is empty on BR pages).
No key, no login."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from . import domain as _dom
from . import http as _http

INSTRUCTIONS = """\
Unofficial read-only MCP server for BR (br.de) — the Bayerischer
Rundfunk, Bavaria's public broadcaster and ARD member — via its
official RSS feeds (no key, no login) and article pages. The BR24
news ticker (7 items, the description IS the whole short news text),
news by category (bayern, wissen, sport, kultur, wirtschaft — 50
items each, with per-article URLs and images), keyword search across
all news feeds, full article text (server-rendered <article>
paragraphs — the JSON-LD articleBody is empty on BR pages), the
Bayern 1 / Bayern 2 radio story feeds, and the Verkehrsmeldungen
traffic feed. NOTE: ticker items link to the shared ticker index
page (index.html#n1...), not to per-item articles, so br_get_article
refuses ticker links — their full text is already in the feed
description. Traffic items link to the legacy br-online.de host and
are self-contained; they are never fetched. BR is public
broadcasting: sampled pages are free; a page that is not free
returns paywalled=true with the teaser, never fabricated text.
Built by Mohammad Abbasi (mohammad-abbasi-sh) — https://almanibama.ir · \
https://mabbasi.ir — Germany MCP factory.\
"""


_SOURCE = "www.br.de"
_DISCLAIMER = "Unofficial read-only data from BR's public RSS feeds and article pages; verify on the site before acting on it."


def _envelope() -> dict:
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": _SOURCE,
        "disclaimer": _DISCLAIMER,
    }


def _ok(payload: dict) -> str:
    return json.dumps({**_envelope(), **payload}, ensure_ascii=False)


def _err(e: Exception) -> str:
    return _ok({"error": str(e)})


mcp = FastMCP("br-mcp", instructions=INSTRUCTIONS)


def _feed(url: str, limit: int) -> dict:
    """Fetch one BR RSS 2.0 feed and return its items, newest first, capped."""
    parsed = _dom.parse_rss(_http.fetch_feed(url))
    items = parsed["items"][:limit]
    return {
        "feed_title": parsed["feed_title"],
        "total_results": parsed["count"],
        "count": len(items),
        "items": items,
    }


@mcp.tool()
def br_headlines(limit: int = 10) -> str:
    """Top BR24 news ticker items (official RSS feed, ~7 items), newest first.
limit: 1..150 (default 10). Every item's description IS the whole
short news text — ticker items have no per-item article URL (they
all link to the shared ticker index page), so br_get_article does
not apply to them."""
    try:
        lim = _dom.validate_limit(limit)
        out = _feed(_dom.HEADLINES_FEED, lim)
    except (_http.BrError, ValueError) as e:
        return _err(e)
    return _ok(out)


@mcp.tool()
def br_news_by_category(category: str, limit: int = 10) -> str:
    """Newest BR news of one category, from its own official RSS feed
(50 items each). category: "bayern", "wissen", "sport", "kultur" or
"wirtschaft". limit: 1..150 (default 10). Items carry title, link
(a per-article URL for br_get_article), teaser, category, image and
publish time."""
    try:
        cat = _dom.validate_category(category)
        lim = _dom.validate_limit(limit)
        out = _feed(_dom.CATEGORIES[cat], lim)
        out["category"] = cat
    except (_http.BrError, ValueError) as e:
        return _err(e)
    return _ok(out)


@mcp.tool()
def br_search_news(query: str, limit: int = 10) -> str:
    """Search BR news by keyword (title + teaser) across the ticker and
all five category feeds. query: free text, e.g. "München" or
"Bundesliga". limit: 1..150 (default 10). Searches ~257 items
client-side, newest first, de-duplicated by link."""
    try:
        if not (query or "").strip():
            return _ok({"error": "query must not be empty"})
        lim = _dom.validate_limit(limit)
        all_items: list[dict] = []
        urls = [_dom.HEADLINES_FEED] + list(_dom.CATEGORIES.values())
        for url in urls:
            parsed = _dom.parse_rss(_http.fetch_feed(url))
            all_items.extend(parsed["items"])
        found = _dom.dedupe_sort(_dom.search_items(all_items, query.strip()))
        out = {
            "query": query.strip(),
            "total_results": len(found),
            "count": min(lim, len(found)),
            "items": found[:lim],
        }
    except (_http.BrError, ValueError) as e:
        return _err(e)
    return _ok(out)


@mcp.tool()
def br_get_article(url: str) -> str:
    """Full text of one BR article page (server-rendered <article>
paragraphs — the JSON-LD articleBody is empty on BR pages). url: a
www.br.de article URL, e.g. from br_news_by_category
(/nachrichten/<category>/<slug>,<id>) or a radio story page ending
in .html. Returns title, author, publish time, the body text and
its word count. Ticker links (index.html#n1...) are refused — the
ticker item's full text is already in its feed description. A page
that is not freely accessible returns paywalled=true with the teaser
only. Nothing is ever fabricated."""
    try:
        if not (url or "").strip():
            return _ok({"error": "url must not be empty"})
        url = url.strip()
        article = _dom.parse_article(_http.fetch_article(url))
        paywalled = article["paywalled"]
        note = ""
        if paywalled:
            note = (
                "This article is not freely accessible: only the teaser "
                "is available."
            )
        elif article["kind"] == "video":
            note = (
                "Video page: the description is the whole freely "
                "available text; watch the video at video_url."
            )
        elif article["teaser_only"]:
            note = (
                "Only the teaser is available for this item; the teaser "
                "is the whole freely available text."
            )
        out = {
            "url": url,
            "title": article["title"],
            "author": article["author"],
            "published": article["published"],
            "kind": article["kind"],
            "paywalled": paywalled,
            "teaser_only": article["teaser_only"],
            "word_count": article["word_count"],
            "body": article["body"],
            "description": article["description"],
            "video_url": article["video_url"],
            "duration": article["duration"],
            "note": note,
        }
    except (_http.BrError, ValueError) as e:
        return _err(e)
    return _ok(out)


@mcp.tool()
def br_radio(station: str = "bayern1", limit: int = 10) -> str:
    """Latest stories from a BR radio station's official RSS feed.
station: "bayern1" or "bayern2" (default "bayern1"). limit: 1..150
(default 10). Items carry title, link (a .html story page for
br_get_article), teaser and publish time."""
    try:
        st = _dom.validate_station(station)
        lim = _dom.validate_limit(limit)
        parsed = _dom.parse_rdf(_http.fetch_feed(_dom.RADIO[st]))
        items = parsed["items"][:lim]
        for it in items:
            it["station"] = st
        out = {
            "station": st,
            "feed_title": parsed["feed_title"],
            "total_results": parsed["count"],
            "count": len(items),
            "items": items,
        }
    except (_http.BrError, ValueError) as e:
        return _err(e)
    return _ok(out)


@mcp.tool()
def br_traffic(limit: int = 10) -> str:
    """Current Verkehrsmeldungen (traffic reports) from BR's official
RSS feed. limit: 1..150 (default 10). Each item's description is the
whole message (road, direction, location, time). Items link to the
legacy br-online.de host and are never fetched."""
    try:
        lim = _dom.validate_limit(limit)
        out = _feed(_dom.TRAFFIC_FEED, lim)
    except (_http.BrError, ValueError) as e:
        return _err(e)
    return _ok(out)


@mcp.tool()
def br_health() -> str:
    """Check whether the BR24 ticker feed is reachable right now.

    Returns status ok (HTTP 200), blocked (HTTP 403/429 — bot wall or
    rate limit) or error, plus the HTTP status and the probed URL.
    One polite request; it does not fetch any listings."""
    return _ok(_http.health_check())


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    sys.exit(main())
