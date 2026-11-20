"""HTTP layer for br_mcp — plain httpx GETs against www.br.de and
nachrichtenfeeds.br.de.

Endpoints, all public, no key, no login:
- the official RSS feeds: the BR24 news ticker
  https://www.br.de/nachrichten/meldungen/nachrichten-bayerischer-rundfunk100~newsRss.xml,
  the five category feeds under
  https://nachrichtenfeeds.br.de/rss/nachrichten/kategorien/<cat>,
  the Bayern 1 / Bayern 2 radio story feeds (RSS 1.0) and the
  Verkehrsmeldungen feed
  https://www.br.de/verkehr-static/verkehrsmeldungen-rss.xml
- article pages: https://www.br.de/nachrichten/<cat>/<slug>,<id>
  and radio/TV pages ending in .html — the full text is read from
  the server-rendered <article> paragraphs (the JSON-LD articleBody
  is empty on BR pages); see domain.parse_article.

Only www.br.de and nachrichtenfeeds.br.de are ever fetched. The
ticker feed's items link to the ticker index page
(/nachrichten/meldungen/index.html#n1..) — that is not an article
and is refused by fetch_article; the traffic feed's items link to
the legacy br-online.de host and are never fetched either.
"""
from __future__ import annotations

import os
import ssl
import time
from urllib.parse import urlparse

import httpx

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
TIMEOUT = 25.0
ALLOWED_HOSTS = ("www.br.de", "nachrichtenfeeds.br.de")
HEALTH_URL = (
    "https://www.br.de/nachrichten/meldungen/"
    "nachrichten-bayerischer-rundfunk100~newsRss.xml"
)


class BrError(RuntimeError):
    pass


def _verify():
    """TLS trust store: the OS bundle when present, else httpx/certifi.

    The OS bundle matters behind MITM egress proxies (their CA is in the
    system store, not in certifi) and is the right default on Linux
    anyway; on systems without it we fall back to certifi.
    """
    for path in (
        "/etc/ssl/certs/ca-certificates.crt",
        ssl.get_default_verify_paths().openssl_cafile,
    ):
        if path and os.path.exists(path):
            return ssl.create_default_context(cafile=path)
    return True


def _client(accept: str) -> httpx.Client:
    # NOTE: we read the proxy URL from the environment but never log it.
    # trust_env=False because httpx fails to parse bracketed IPv6 entries
    # (e.g. [::1]) that some environments put in no_proxy.
    proxy = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")
    return httpx.Client(
        headers={"User-Agent": UA, "Accept": accept},
        timeout=TIMEOUT,
        proxy=proxy or None,
        trust_env=False,
        verify=_verify(),
        follow_redirects=True,
    )


def _check_host(url: str) -> None:
    host = (urlparse(url).netloc or "").lower()
    if host not in ALLOWED_HOSTS:
        raise BrError(
            f"only {', '.join(ALLOWED_HOSTS)} pages are fetched "
            f"(got {host or url!r})"
        )


def _get(url: str, accept: str) -> str:
    """GET with one retry on 429/5xx and on transient network errors."""
    _check_host(url)
    last_exc: Exception | None = None
    r: httpx.Response | None = None
    for attempt in range(2):
        try:
            with _client(accept) as c:
                r = c.get(url)
        except httpx.HTTPError as e:
            last_exc = e
            if attempt == 0:
                time.sleep(1.0)
                continue
            raise BrError(f"network error fetching {url}: {e}") from e
        if r.status_code in (429, 500, 502, 503):
            if attempt == 0:
                time.sleep(1.0)
                continue
        break
    assert r is not None  # loop always assigns r or raises
    if r.status_code == 403:
        raise BrError(
            f"www.br.de returned HTTP 403 for {url} (bot wall) — try again later"
        )
    if r.status_code == 429:
        raise BrError(
            "www.br.de rate-limited the request (HTTP 429) — try again later"
        )
    if r.status_code != 200:
        raise BrError(f"www.br.de returned HTTP {r.status_code} for {url}")
    return r.text


def fetch_feed(url: str) -> str:
    """GET an official BR RSS feed; returns the raw XML text."""
    host = (urlparse(url).netloc or "").lower()
    path = urlparse(url).path
    ok = (
        host in ALLOWED_HOSTS
        and (
            path.endswith(".xml")
            or path.startswith("/rss/nachrichten/kategorien/")
        )
    )
    if not ok:
        raise BrError(f"only BR RSS feed URLs are fetched (got {url!r})")
    return _get(url, "application/rss+xml, application/xml, text/xml, */*")


def fetch_article(url: str) -> str:
    """GET one www.br.de article page; returns the raw HTML text.

    Article URLs are /nachrichten/<category>/<slug>,<id> or pages
    ending in .html (radio/TV stories). The ticker index page and
    any URL with a fragment are refused: ticker items carry their
    whole short text in the feed description already.
    """
    parsed = urlparse(url)
    if parsed.fragment:
        raise BrError(
            "ticker links (index.html#n1...) are not articles — the "
            "item's full short text is already in its feed description "
            f"(got {url!r})"
        )
    path = parsed.path
    if path == "/nachrichten/meldungen/index.html":
        raise BrError(
            "the BR24 ticker index page is not an article — the ticker "
            "items' full short text is already in their feed descriptions"
        )
    if not (path.startswith("/nachrichten/") or path.endswith(".html")):
        raise BrError(
            "only www.br.de article URLs (/nachrichten/... or pages "
            f"ending in .html) are fetched (got {url!r})"
        )
    return _get(url, "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")


def health_check() -> dict:
    """One polite probe of the source feed.

    Returns {"status": "ok"|"blocked"|"error", "http_status": int|None,
    "url": ..., "detail": ...}. Used by the `br_health` tool
    and the daily smoke CI.
    """
    url = HEALTH_URL
    try:
        fetch_feed(url)
    except BrError as e:
        msg = str(e)
        if "403" in msg:
            return {"status": "blocked", "http_status": 403, "url": url, "detail": msg}
        if "429" in msg:
            return {"status": "blocked", "http_status": 429, "url": url, "detail": msg}
        return {"status": "error", "http_status": None, "url": url, "detail": msg}
    return {"status": "ok", "http_status": 200, "url": url}
