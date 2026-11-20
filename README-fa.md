# br-mcp 📻

mcp-name: io.github.mohammad-abbasi-sh/br-mcp

سرور MCP غیررسمی و **فقط‌خواندنی** برای **[BR](https://www.br.de)** — رادیو-تلویزیون بایرن (Bayerischer Rundfunk)، رسانهٔ عمومی ایالت بایرن و عضو ARD — از طریق فیدهای رسمی RSS (تیکر خبری BR24، پنج فید دسته‌بندی در nachrichtenfeeds.br.de، فیدهای رادیویی Bayern 1 و Bayern 2، و فید گزارش‌های ترافیک) و صفحات مقالات که متن کامل آن‌ها از پاراگراف‌های `<article>` رندرشده در سرور خوانده می‌شود (`articleBody` در JSON-LD در صفحات BR خالی است). تیترهای برتر تیکر، اخبار بر اساس دسته (bayern، wissen، sport، kultur، wirtschaft)، جست‌وجوی کلیدواژه، متن کامل مقالات، مطالب رادیویی و گزارش‌های ترافیک. بدون کلید، بدون ورود.

> ساختهٔ محمد عباسی در چارچوب «کارخانهٔ MCP آلمان» (خط تولیدی به سبک سپهر). وابسته به BR یا ARD نیست.

## برای ایجنت‌های هوش مصنوعی

در پیکربندی کلاینت MCP اضافه کنید (stdio):

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

یا اجرای محلی: `python -m br_mcp.server` (نیازمند `mcp<2` و `httpx`).

## ابزارها

| ابزار | توضیح |
|------|-------|
| `br_headlines` | تیترهای برتر تیکر BR24 (فید رسمی RSS، حدود ۷ مورد)، تازه‌ترین اول — `limit` ۱ تا ۱۵۰. توضیح هر مورد، خودِ خبر کوتاه است |
| `br_news_by_category` | تازه‌ترین اخبار یک دسته، از فید رسمی خودش (هر دسته ۵۰ مورد) — `category`: ‏«bayern»، ‏«wissen»، ‏«sport»، ‏«kultur»، ‏«wirtschaft»، `limit` ۱ تا ۱۵۰ |
| `br_search_news` | جست‌وجوی اخبار با کلیدواژه (عنوان + تیزر) در تیکر و هر پنج فید دسته — `query` (مثلاً «München»)، `limit` ۱ تا ۱۵۰ |
| `br_get_article` | متن کامل یک مقالهٔ BR (پاراگراف‌های `<article>` رندرشده در سرور) — `url`: آدرس مقاله در www.br.de به شکل /nachrichten/‎<دسته>/‎<slug>‎,‎<id> یا صفحهٔ رادیویی با پسوند .html. لینک‌های تیکر رد می‌شوند (متن کاملشان در توضیح فید هست)؛ صفحهٔ غیررایگان فقط تیزر را برمی‌گرداند (`paywalled: true`) |
| `br_radio` | تازه‌ترین مطالب از فید رسمی RSS یکی از ایستگاه‌های رادیویی BR — `station`: ‏«bayern1» یا «bayern2»، `limit` ۱ تا ۱۵۰ |
| `br_traffic` | گزارش‌های جاری ترافیک (Verkehrsmeldungen) از فید رسمی RSS در BR — `limit` ۱ تا ۱۵۰. توضیح هر مورد، خودِ پیام است |
| `br_health` | بررسی دسترسی به فید (ok / blocked / error) — یک درخواست مؤدبانه |

نمونهٔ خروجی (`br_headlines` با `limit` برابر ۲):

```json
{"feed_title": "Die Nachrichten des Bayerischen Rundfunks", "total_results": 7, "count": 2,
 "items": [
  {"title": "Bundesrat beschließt Frühstartrente",
   "link": "https://www.br.de/nachrichten/meldungen/index.html#n1",
   "description": "Frühstart-Rente kann in Kraft treten: Kinder bekommen künftig als Startkapital für die private Altersvorsorge pro Monat 10 Euro vom Staat. ...",
   "published": "2026-11-20T10:13:06+00:00", "category": null, "image_url": null},
  ...]}
```

نکته‌ها:
- سرور **فیدهای رسمی RSS** را می‌خواند (تیکر حدود ۷ مورد، فیدهای دسته هر کدام ۵۰ مورد، فیدهای رادیویی ۸۰/۴۱ مورد، ترافیک حدود ۱۴ مورد، تأیید زنده در ۲۰۲۶-۱۱-۲۰). جست‌وجو روی فیدِ دریافت‌شده انجام می‌شود.
- فید تیکر **برای هر مورد آدرس مقاله ندارد**: همهٔ موردها به صفحهٔ مشترک فهرست تیکر (`index.html#n1` و …) لینک می‌دهند و توضیح، خودِ خبر کوتاه است — پس `br_get_article` لینک‌های تیکر را رد می‌کند. موردهای دسته آدرس مقالهٔ مخصوص خودشان، `<category>` و تصویر رسانه‌ای دارند.
- **متن مقالات، صادقانه:** صفحات مقالات BR یک `articleBody` خالی در JSON-LD دارند، پس متن همیشه از پاراگراف‌های `<article>` رندرشده در سرور خوانده می‌شود (در نمونه ۶۸۴ کلمه، با حذف سطرهای سربرگ، تیزر و «Über dieses Thema berichtet»). صفحات مقاله ممکن است ویدیو هم داشته باشند — صفحه‌ای که بلوک NewsArticle دارد، همیشه مقاله شمرده می‌شود، نه صفحهٔ ویدیویی. BR رسانهٔ عمومی است: نمونه‌ها رایگان‌اند؛ صفحهٔ غیررایگان فقط تیزر را برمی‌گرداند (`paywalled: true`).
- فیدهای رادیویی لینک‌های خارجی هم دارند (۱۳ مورد از ۸۰ مورد Bayern 1 به قسمت‌های ARD Audiothek یا ریلز اینستاگرام می‌روند) و موردهای ترافیک به هاست قدیمی br-online.de لینک می‌دهند — هر دو همان‌طور که هستند برگردانده می‌شوند و `br_get_article` هرگز آن‌ها را نمی‌خواند.
- فقط پنج اسلاگ دسته وجود دارد (bayern، wissen، sport، kultur، wirtschaft) — deutschland، welt، politik، wetter، verkehr و اسلاگ‌های منطقه‌ای در سایت زنده همه 404 می‌دهند.
- داده‌ها: فیدهای عمومی RSS و صفحات مقالات BR — بدون کلید، بدون ورود، فقط‌خواندنی.

## توسعه

```bash
python3 -m venv .venv && .venv/bin/pip install "mcp<2" httpx pytest
.venv/bin/pip install -e .
.venv/bin/python -m pytest tests/ -q
```

- `tests/test_domain.py` — آفلاین؛ فیدهای واقعیِ ذخیره‌شده (تیکر، دسته، رادیو و ترافیک) و یک صفحهٔ مقالهٔ واقعی را تجزیه می‌کند (مقالهٔ wissen با متن JSON-LD خالی و VideoObject جاسازی‌شده)
- `tests/test_live.py` — درخواست‌های زندهٔ محتاطانه به www.br.de و nachrichtenfeeds.br.de

تست‌ها: ۳۲/۳۲ سبز (۲۵ آفلاین + ۷ زنده، ۲۰۲۶-۱۱-۲۰).

## مجوز

[PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/) — رایگان برای استفادهٔ شخصی و غیرتجاری؛ استفادهٔ تجاری نیازمند مجوز جداگانه است (به LICENSE نگاه کنید).

---

ساختهٔ [محمد عباسی](https://github.com/mohammad-abbasi-sh) — [آلمانی‌باما](https://almanibama.ir) · [mabbasi.ir](https://mabbasi.ir)
