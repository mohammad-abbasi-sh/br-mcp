# br-mcp 📻

mcp-name: io.github.mohammad-abbasi-sh/br-mcp

Unofficial **read-only** MCP server for **[BR](https://www.br.de)** — the Bayerischer Rundfunk, Bavaria's public broadcaster and ARD member — via its official RSS feeds (the BR24 news ticker, five category feeds under nachrichtenfeeds.br.de, the Bayern 1 / Bayern 2 radio story feeds, and the Verkehrsmeldungen feed) and article pages, whose full text is read from the server-rendered `<article>` paragraphs (the JSON-LD `articleBody` is empty on BR pages). Top ticker headlines, news by category (bayern, wissen, sport, kultur, wirtschaft), keyword search, full article text, radio stories, and traffic reports. No key, no login.

> Built by Mohammad Abbasi as part of the "Germany MCP factory" (Sepehr-style pipeline). Not affiliated with BR or ARD.

## For AI agents

Add to your MCP client config (stdio):

```json
{
  "mcpServers": {
    "br": {
      "command": "uvx",
      "args": ["br-mcp==0.1.0"]
    }
  }
}
```

Or run locally: `python -m br_mcp.server` (needs `mcp<2`, `httpx`).

## Tools

| Tool | Description |
|------|-------------|
| `br_headlines` | Top BR24 news ticker items (official RSS feed, ~7 items), newest first — `limit` 1..150. Each item's description IS the whole short news text |
| `br_news_by_category` | Newest news of one category, from its own official RSS feed (50 items each) — `category`: "bayern", "wissen", "sport", "kultur", "wirtschaft", `limit` 1..150 |
| `br_search_news` | Search news by keyword (title + teaser) across the ticker and all five category feeds — `query` (e.g. "München"), `limit` 1..150 |
| `br_get_article` | Full text of one BR article page (server-rendered `<article>` paragraphs) — `url`: a www.br.de article URL (/nachrichten/<category>/<slug>,<id>) or a radio story page ending in .html. Ticker links are refused (their full text is already in the feed description); a non-free page returns `paywalled: true` with the teaser only |
| `br_radio` | Latest stories from a BR radio station's official RSS feed — `station`: "bayern1" or "bayern2", `limit` 1..150 |
| `br_traffic` | Current Verkehrsmeldungen (traffic reports) from BR's official RSS feed — `limit` 1..150. Each item's description is the whole message |
| `br_health` | Reachability probe (ok / blocked / error) — one polite request |

Example output (`br_headlines`, `limit` 2):

```json
{"feed_title": "Die Nachrichten des Bayerischen Rundfunks", "total_results": 7, "count": 2,
 "items": [
  {"title": "Bundesrat beschließt Frühstartrente",
   "link": "https://www.br.de/nachrichten/meldungen/index.html#n1",
   "description": "Frühstart-Rente kann in Kraft treten: Kinder bekommen künftig als Startkapital für die private Altersvorsorge pro Monat 10 Euro vom Staat. ...",
   "published": "2026-11-20T10:13:06+00:00", "category": null, "image_url": null},
  ...]}
```

Notes:
- The server reads the **official RSS feeds** (ticker ~7 items, category feeds 50 items each, radio feeds 80/41 items, traffic ~14 items, verified live 2026-11-20). Search runs client-side over the fetched feeds.
- The ticker feed carries **no per-item article URLs**: every item links to the shared ticker index page (`index.html#n1`…), and the description is the whole short news text — so `br_get_article` refuses ticker links and says so. Category items carry per-article URLs, a `<category>` and a media image.
- **Article text, honestly:** BR article pages carry an EMPTY JSON-LD `articleBody`, so the body is always read from the server-rendered `<article>` paragraphs (684 words sampled, header / teaser / "Über dieses Thema berichtet" lines filtered out). Article pages may embed a video — a page with a NewsArticle block is still treated as an article, never as a video page. BR is public broadcasting: sampled pages are free; a page that is not free returns `paywalled: true` with the teaser only.
- The radio feeds mix in off-site links (13 of 80 Bayern 1 items point at ARD Audiothek episodes or Instagram reels) and the traffic feed's items link to the legacy br-online.de host — both are returned as-is and never fetched by `br_get_article`.
- Only five category slugs exist (bayern, wissen, sport, kultur, wirtschaft) — deutschland, welt, politik, wetter, verkehr and the regional slugs all 404 on the live site.
- Data: BR public RSS feeds and article pages — no key, no login, read-only.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install "mcp<2" httpx pytest
.venv/bin/pip install -e .
.venv/bin/python -m pytest tests/ -q
```

- `tests/test_domain.py` — offline, parses the real captured ticker, category, radio and traffic feeds plus one real article page (wissen NewsArticle with empty JSON-LD body and an embedded VideoObject)
- `tests/test_live.py` — cautious live requests against www.br.de and nachrichtenfeeds.br.de

Tests: 32/32 green (25 offline + 7 live, 2026-11-20).

## License

[PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) — free for personal and non-commercial use; commercial use needs a separate license (see LICENSE).

---

Built by [Mohammad Abbasi](https://github.com/mohammad-abbasi-sh) — [Almanibama](https://almanibama.ir) · [mabbasi.ir](https://mabbasi.ir)
