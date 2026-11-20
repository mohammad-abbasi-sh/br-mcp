# br-mcp 📻

mcp-name: io.github.mohammad-abbasi-sh/br-mcp

Inoffizieller **Read-only**-MCP-Server für **[BR](https://www.br.de)** — den Bayerischen Rundfunk, öffentlich-rechtlicher Sender Bayerns und ARD-Mitglied — über die offiziellen RSS-Feeds (BR24-Nachrichtenticker, fünf Kategorien-Feeds unter nachrichtenfeeds.br.de, die Bayern-1-/Bayern-2-Radio-Feeds und die Verkehrsmeldungen) und Artikelseiten, deren Volltext aus den serverseitig gerenderten `<article>`-Absätzen gelesen wird (das JSON-LD-`articleBody` ist auf BR-Seiten leer). Top-Ticker-Meldungen, Nachrichten nach Kategorie (bayern, wissen, sport, kultur, wirtschaft), Stichwortsuche, Volltexte von Artikeln, Radio-Geschichten und Verkehrsmeldungen. Kein Schlüssel, kein Login.

> Gebaut von Mohammad Abbasi als Teil der "Germany MCP factory" (Sepehr-ähnliche Pipeline). Nicht mit BR oder ARD verbunden.

## Für KI-Agenten

In die MCP-Client-Konfiguration eintragen (stdio):

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

Oder lokal starten: `python -m br_mcp.server` (benötigt `mcp<2`, `httpx`).

## Tools

| Tool | Beschreibung |
|------|-------------|
| `br_headlines` | Top-Meldungen des BR24-Tickers (offizieller RSS-Feed, ~7 Einträge), neueste zuerst — `limit` 1..150. Die Beschreibung jedes Eintrags IST die ganze Kurzmeldung |
| `br_news_by_category` | Neueste Nachrichten einer Kategorie, aus dem eigenen offiziellen RSS-Feed (je 50 Einträge) — `category`: "bayern", "wissen", "sport", "kultur", "wirtschaft", `limit` 1..150 |
| `br_search_news` | Stichwortsuche in den Nachrichten (Titel + Teaser) über Ticker und alle fünf Kategorien-Feeds — `query` (z. B. "München"), `limit` 1..150 |
| `br_get_article` | Volltext einer BR-Artikelseite (serverseitig gerenderte `<article>`-Absätze) — `url`: eine www.br.de-Artikel-URL (/nachrichten/<kategorie>/<slug>,<id>) oder eine Radio-Seite mit Endung .html. Ticker-Links werden abgelehnt (ihr Volltext steht schon in der Feed-Beschreibung); eine nicht frei zugängliche Seite liefert `paywalled: true` und nur den Teaser |
| `br_radio` | Neueste Geschichten aus dem offiziellen RSS-Feed eines BR-Radiosenders — `station`: "bayern1" oder "bayern2", `limit` 1..150 |
| `br_traffic` | Aktuelle Verkehrsmeldungen aus dem offiziellen RSS-Feed des BR — `limit` 1..150. Die Beschreibung jedes Eintrags ist die ganze Meldung |
| `br_health` | Erreichbarkeitsprüfung (ok / blocked / error) — eine höfliche Anfrage |

Beispielausgabe (`br_headlines`, `limit` 2):

```json
{"feed_title": "Die Nachrichten des Bayerischen Rundfunks", "total_results": 7, "count": 2,
 "items": [
  {"title": "Bundesrat beschließt Frühstartrente",
   "link": "https://www.br.de/nachrichten/meldungen/index.html#n1",
   "description": "Frühstart-Rente kann in Kraft treten: Kinder bekommen künftig als Startkapital für die private Altersvorsorge pro Monat 10 Euro vom Staat. ...",
   "published": "2026-11-20T10:13:06+00:00", "category": null, "image_url": null},
  ...]}
```

Hinweise:
- Der Server liest die **offiziellen RSS-Feeds** (Ticker ~7 Einträge, Kategorien-Feeds je 50 Einträge, Radio-Feeds 80/41 Einträge, Verkehr ~14 Einträge, live verifiziert 2026-11-20). Die Suche läuft clientseitig über die geladenen Feeds.
- Der Ticker-Feed trägt **keine Artikel-URLs pro Eintrag**: alle Einträge verlinken auf die gemeinsame Ticker-Indexseite (`index.html#n1`…), und die Beschreibung ist die ganze Kurzmeldung — `br_get_article` lehnt Ticker-Links daher ab. Kategorien-Einträge tragen eigene Artikel-URLs, eine `<category>` und ein Medienbild.
- **Artikeltexte, ehrlich:** BR-Artikelseiten tragen ein LEERES JSON-LD-`articleBody`, der Text wird daher immer aus den serverseitig gerenderten `<article>`-Absätzen gelesen (684 Wörter in der Stichprobe, Kopf- / Teaser- / "Über dieses Thema berichtet"-Zeilen herausgefiltert). Artikelseiten können ein Video einbetten — eine Seite mit NewsArticle-Block gilt trotzdem als Artikel, nie als Videoseite. BR ist öffentlich-rechtlich: die Stichproben sind frei; eine nicht freie Seite liefert `paywalled: true` und nur den Teaser.
- Die Radio-Feeds mischen externe Links ein (13 von 80 Bayern-1-Einträgen verweisen auf ARD-Audiothek-Folgen oder Instagram-Reels) und die Verkehrsmeldungen verlinken auf den alten br-online.de-Host — beides wird unverändert zurückgegeben und von `br_get_article` nie abgerufen.
- Nur fünf Kategorien-Slugs existieren (bayern, wissen, sport, kultur, wirtschaft) — deutschland, welt, politik, wetter, verkehr und die regionalen Slugs liefern auf der Live-Seite alle 404.
- Daten: öffentliche BR-RSS-Feeds und Artikelseiten — kein Schlüssel, kein Login, nur lesend.

## Entwicklung

```bash
python3 -m venv .venv && .venv/bin/pip install "mcp<2" httpx pytest
.venv/bin/pip install -e .
.venv/bin/python -m pytest tests/ -q
```

- `tests/test_domain.py` — offline, parst die echten, gespeicherten Ticker-, Kategorien-, Radio- und Verkehrs-Feeds sowie eine echte Artikelseite (wissen-NewsArticle mit leerem JSON-LD-Text und eingebettetem VideoObject)
- `tests/test_live.py` — vorsichtige Live-Anfragen an www.br.de und nachrichtenfeeds.br.de

Tests: 32/32 grün (25 offline + 7 live, 2026-11-20).

## Lizenz

[PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) — frei für private und nicht-kommerzielle Nutzung; kommerzielle Nutzung braucht eine separate Lizenz (siehe LICENSE).

---

Gebaut von [Mohammad Abbasi](https://github.com/mohammad-abbasi-sh) — [Almanibama](https://almanibama.ir) · [mabbasi.ir](https://mabbasi.ir)
