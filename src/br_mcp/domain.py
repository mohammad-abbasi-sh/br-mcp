"""Domain logic: shape br.de's official RSS feeds and article pages
into compact dicts (stdlib only).

Data source: the official Bayerischer Rundfunk RSS feeds (no key, no
login) — the BR24 news ticker
(https://www.br.de/nachrichten/meldungen/nachrichten-bayerischer-rundfunk100~newsRss.xml),
one category feed per topic under nachrichtenfeeds.br.de
(bayern, wissen, sport, kultur, wirtschaft, 50 items each), the
Bayern 1 / Bayern 2 radio story feeds (RSS 1.0 / RDF) and the
Verkehrsmeldungen feed — plus article pages, whose full text lives
in the server-rendered <article> paragraphs.

Honest limitations (verified live 2026-11-20):
- The ticker feed carries only ~7 items and every item links to the
  same ticker index page (index.html#n1..#n7) — there are no
  per-item article URLs; the description IS the whole short news
  text, so br_get_article refuses ticker links and says so.
- The category feeds carry per-article URLs
  (/nachrichten/<cat>/<slug>,<id>) with title, teaser, <category>
  and a media:content image — but no author.
- The JSON-LD NewsArticle block on BR article pages carries an
  EMPTY articleBody, so the body is always read from the
  server-rendered <article> paragraphs (19 <p> sampled, header /
  teaser / "Über dieses Thema berichtet" lines filtered out).
- BR is public broadcasting: sampled pages carry no paywall and no
  isAccessibleForFree flag (absent = free); the flag is still
  honoured if a page ever sets it to false.
- The traffic feed's items link to the legacy br-online.de host and
  are self-contained (the description is the whole message);
  br_get_article never fetches br-online.de.
- The radio feeds mix in off-site links (13 of 80 Bayern 1 items
  point at ARD Audiothek episodes or Instagram reels) — returned
  as-is, never fetched by br_get_article.
- Only five category slugs exist (bayern, wissen, sport, kultur,
  wirtschaft) — deutschland, welt, politik, wetter, verkehr and the
  seven regional slugs all 404.
"""
from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

BASE = "https://www.br.de"
HEADLINES_FEED = (
    f"{BASE}/nachrichten/meldungen/"
    "nachrichten-bayerischer-rundfunk100~newsRss.xml"
)
TRAFFIC_FEED = f"{BASE}/verkehr-static/verkehrsmeldungen-rss.xml"

# Category feeds — one per topic (verified 200, 50 items each,
# 2026-11-20). The feed's <category> matches the slug's label.
CATEGORIES = {
    "bayern": "https://nachrichtenfeeds.br.de/rss/nachrichten/kategorien/bayern",
    "wissen": "https://nachrichtenfeeds.br.de/rss/nachrichten/kategorien/wissen",
    "sport": "https://nachrichtenfeeds.br.de/rss/nachrichten/kategorien/sport",
    "kultur": "https://nachrichtenfeeds.br.de/rss/nachrichten/kategorien/kultur",
    "wirtschaft": (
        "https://nachrichtenfeeds.br.de/rss/nachrichten/kategorien/wirtschaft"
    ),
}

# Radio story feeds (RSS 1.0 / RDF, verified 200, 2026-11-20).
# Bayern 2's feed redirects /bayern-zwei108~rss.xml -> the -120 URL
# below; the canonical URL is used directly.
RADIO = {
    "bayern1": f"{BASE}/radio/bayern1/bayern-eins108~rss.xml",
    "bayern2": f"{BASE}/radio/bayern2/bayern-zwei-120~rss.xml",
}

# Namespaces used by the RSS 1.0 (RDF) radio feeds.
_RSS1 = "http://purl.org/rss/1.0/"
_MRSS = "http://search.yahoo.com/mrss/"


def validate_limit(limit: int) -> int:
    """Clamp/validate the page size (feeds carry 7-80 items)."""
    if not 1 <= limit <= 150:
        raise ValueError(f"limit out of range: {limit} (expected 1..150)")
    return limit


def validate_category(category: str) -> str:
    """Normalise a category name to one of the five category feeds."""
    c = (category or "").strip().casefold()
    if c not in CATEGORIES:
        raise ValueError(
            f"unknown category: {category!r} (expected one of "
            f"{', '.join(sorted(CATEGORIES))})"
        )
    return c


def validate_station(station: str) -> str:
    """Normalise a radio station name to one of the two radio feeds."""
    s = (station or "").strip().casefold()
    if s not in RADIO:
        raise ValueError(
            f"unknown station: {station!r} (expected one of "
            f"{', '.join(sorted(RADIO))})"
        )
    return s


def _text(elem, tag: str) -> str:
    child = elem.find(tag)
    if child is None or child.text is None:
        return ""
    return html.unescape(child.text).strip()


def _iso(date_text: str) -> str | None:
    if not date_text:
        return None
    text = date_text.strip()
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(raw: str) -> str:
    text = _TAG_RE.sub("", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _published(item: ET.Element) -> str | None:
    """pubDate (RSS 2.0) or dc:date (RSS 2.0 ticker / RSS 1.0).

    Matched by local name, not namespace: BR's radio feeds declare
    the dc namespace with a typo (dc/elments/1.1/), so a
    URI-exact lookup misses their dates."""
    for child in item:
        local = child.tag.rsplit("}", 1)[-1]
        if local in ("pubDate", "date") and child.text:
            return _iso(child.text)
    return None


def compact_item(item: ET.Element) -> dict:
    """One RSS 2.0 <item>: title, link, description, category,
    image and publish time. The ticker feed's description is the
    whole short news text; category items carry a media image."""
    image = None
    media = item.find(f"{{{_MRSS}}}content")
    if media is not None:
        image = media.get("url") or None
    return {
        "title": _text(item, "title"),
        "link": _text(item, "link"),
        "description": _strip_tags(_text(item, "description")),
        "published": _published(item),
        "category": _text(item, "category") or None,
        "image_url": image,
    }


def parse_rss(xml_text: str) -> dict:
    """Parse an RSS 2.0 feed (ticker, category or traffic) into
    {feed_title, count, items}.

    Raises ValueError on malformed XML or a non-RSS document (e.g. a
    404 error page saved as text).
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ValueError(f"invalid RSS XML: {e}") from e
    channel = root.find("channel")
    if channel is None:
        raise ValueError("unexpected RSS shape: no <channel> element")
    items = [compact_item(it) for it in channel.findall("item")]
    return {
        "feed_title": _text(channel, "title"),
        "count": len(items),
        "items": items,
    }


def parse_rdf(xml_text: str) -> dict:
    """Parse an RSS 1.0 (RDF) feed — the Bayern 1 / Bayern 2 radio
    story feeds — into {feed_title, count, items}. Items carry
    title, link, description and dc:date; category is the station
    subject and is left as None (the tool adds the station)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ValueError(f"invalid RSS XML: {e}") from e
    if root.tag != "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF":
        raise ValueError("unexpected RSS shape: no <rdf:RDF> root element")
    items = []
    for it in root.findall(f"{{{_RSS1}}}item"):
        title = _text(it, f"{{{_RSS1}}}title")
        link = _text(it, f"{{{_RSS1}}}link")
        desc = _strip_tags(_text(it, f"{{{_RSS1}}}description"))
        items.append({
            "title": title,
            "link": link,
            "description": desc,
            "published": _published(it),
            "category": None,
            "image_url": None,
        })
    title = ""
    channel = root.find(f"{{{_RSS1}}}channel")
    if channel is not None:
        title = _text(channel, f"{{{_RSS1}}}title")
    return {"feed_title": title, "count": len(items), "items": items}


_LD_JSON_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
    re.S | re.I,
)
_ARTICLE_RE = re.compile(r"<article[^>]*>(.*?)</article>", re.S | re.I)
_P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_OG_DESC_RE = re.compile(
    r'<meta[^>]+property="og:description"[^>]+content="([^"]*)"',
    re.S | re.I,
)


def _author_name(raw) -> str:
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, dict):
        return str(raw.get("name") or "").strip()
    if isinstance(raw, list):
        names = [_author_name(a) for a in raw]
        return ", ".join(n for n in names if n)
    return ""


def _is_free(block: dict) -> bool:
    """isAccessibleForFree from a JSON-LD block; absent means free
    (BR pages that carry the field at all set it explicitly)."""
    val = block.get("isAccessibleForFree")
    return True if val is None else bool(val)


def _ssr_body(html_text: str, title: str, description: str) -> str:
    """Body text from the server-rendered <article> paragraphs.

    Filters out the header paragraph (the title), the teaser
    paragraph (a repeat of the description), the "Über dieses Thema
    berichtet: ..." broadcast note and "Stand:" header lines, which
    are metadata, not body. Raises ValueError when no usable body
    paragraphs are found.
    """
    match = _ARTICLE_RE.search(html_text)
    if not match:
        raise ValueError(
            "no article text found on this page (no JSON-LD articleBody "
            "and no <article> body) — the page may be JS-rendered or an "
            "error page"
        )
    paras: list[str] = []
    for raw in _P_RE.findall(match.group(1)):
        text = _strip_tags(raw)
        if not text:
            continue
        if title and text == title:
            continue  # header paragraph: the title again
        if description and text == description:
            continue  # teaser paragraph: the description again
        if text.startswith("Über dieses Thema berichtet:"):
            continue  # broadcast note ("... am 18.11.2026 um 14:46 Uhr")
        if "Stand:" in text and "Uhr" in text and len(text) < 120:
            continue  # header paragraph: title + Stand + author line
        paras.append(text)
    body = "\n\n".join(paras).strip()
    if not body:
        raise ValueError(
            "no article text found on this page (the <article> body is "
            "empty after filtering)"
        )
    return body


def _page_title(html_text: str) -> str:
    match = _TITLE_RE.search(html_text)
    if not match:
        return ""
    title = _strip_tags(match.group(1))
    return re.sub(r"\s*\|\s*BR24\s*$", "", title, flags=re.I)


def parse_article(html_text: str) -> dict:
    """Extract the article from a br.de page.

    Prefers the JSON-LD NewsArticle/Article "articleBody" — but BR
    pages carry an EMPTY articleBody, so in practice the body is
    always read from the server-rendered <article> paragraphs.
    Returns {title, description, body, author, published,
    word_count, teaser_only, paywalled, kind, video_url, duration}.
    Raises ValueError when no usable text is found.
    """
    blocks: list[dict] = []
    for match in _LD_JSON_RE.finditer(html_text):
        try:
            data = json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict):
            blocks.append(data)

    title = _page_title(html_text)
    description = ""
    og = _OG_DESC_RE.search(html_text)
    if og:
        description = html.unescape(og.group(1)).strip()

    for block in blocks:
        body = (block.get("articleBody") or "").strip()
        if not body:
            continue
        description = description or _strip_tags(str(block.get("description") or ""))
        return {
            "title": _strip_tags(str(block.get("headline") or "")) or title,
            "description": description,
            "body": body,
            "author": _author_name(block.get("author")),
            "published": str(block.get("datePublished") or "") or None,
            "word_count": len(body.split()),
            "teaser_only": bool(body) and body == description,
            "paywalled": not _is_free(block),
            "kind": "article",
            "video_url": None,
            "duration": None,
        }

    # A NewsArticle/Article block means the page IS an article — even
    # when it embeds a video (BR article pages carry a VideoObject
    # block too, listed before the NewsArticle block). Only a page
    # with no article block at all is treated as a video page.
    article_block = None
    for block in blocks:
        if block.get("@type") in ("NewsArticle", "Article"):
            article_block = block
            break
    if article_block is not None:
        description = description or _strip_tags(
            str(article_block.get("description") or "")
        )
        body = _ssr_body(html_text, title, description)
        return {
            "title": (
                _strip_tags(str(article_block.get("headline") or "")) or title
            ),
            "description": description,
            "body": body,
            "author": _author_name(article_block.get("author")),
            "published": (
                str(article_block.get("datePublished") or "") or None
            ),
            "word_count": len(body.split()),
            "teaser_only": bool(body) and body == description,
            "paywalled": not _is_free(article_block),
            "kind": "article",
            "video_url": None,
            "duration": None,
        }

    for block in blocks:
        if block.get("@type") != "VideoObject":
            continue
        description = description or _strip_tags(str(block.get("description") or ""))
        return {
            "title": _strip_tags(str(block.get("name") or "")) or title,
            "description": description,
            "body": description,
            "author": "",
            "published": str(block.get("uploadDate") or "") or None,
            "word_count": len(description.split()),
            "teaser_only": True,
            "paywalled": not _is_free(block),
            "kind": "video",
            "video_url": str(block.get("contentUrl") or "") or None,
            "duration": str(block.get("duration") or "") or None,
        }

    body = _ssr_body(html_text, title, description)
    return {
        "title": title,
        "description": description,
        "body": body,
        "author": "",
        "published": None,
        "word_count": len(body.split()),
        "teaser_only": bool(body) and body == description,
        "paywalled": False,
        "kind": "article",
        "video_url": None,
        "duration": None,
    }


def search_items(items: list, query: str) -> list:
    """Case-insensitive substring match over title + description."""
    q = (query or "").strip().casefold()
    if not q:
        raise ValueError("query must not be empty")
    return [
        it for it in items
        if q in (it.get("title") or "").casefold()
        or q in (it.get("description") or "").casefold()
    ]


def dedupe_sort(items: list) -> list:
    """De-duplicate by link, newest first (empty publish time sorts last)."""
    seen: set[str] = set()
    unique: list[dict] = []
    for it in items:
        if it["link"] in seen:
            continue
        seen.add(it["link"])
        unique.append(it)
    unique.sort(key=lambda it: it.get("published") or "", reverse=True)
    return unique
