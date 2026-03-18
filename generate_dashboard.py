from __future__ import annotations

import csv
import datetime as dt
import email.utils
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "dashboard.json"
FEEDS_PATH = ROOT / "config" / "news_feeds.json"
SEED_SYMBOLS_PATH = ROOT / "config" / "seed_symbols.json"

USER_AGENT = "Mozilla/5.0 (compatible; IndiaTradeMarketPulse/1.0; +https://github.com/)"
MAX_NEWS_ITEMS = 8
WATCHLIST_LIMIT = 30
NIFTY_500_URLS = [
    "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",
    "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
]


def http_get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.read()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_feed_timestamp(value: str | None) -> str | None:
    if not value:
        return None

    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)

    return parsed.astimezone(dt.timezone.utc).isoformat()


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


def normalize_whitespace(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def build_summaries(title: str, description: str, source: str) -> tuple[str, str]:
    cleaned_description = normalize_whitespace(description)
    title = normalize_whitespace(title)

    if not cleaned_description:
        short_summary = f"{source} is tracking this development involving {title}."
        detailed_summary = (
            f"{source} is reporting on {title}. The feed entry did not include a full description, "
            "so the dashboard is preserving the headline and direct source link for full context."
        )
        return short_summary, detailed_summary

    sentences = re.split(r"(?<=[.!?])\s+", cleaned_description)
    sentences = [sentence.strip() for sentence in sentences if sentence.strip()]

    short_summary = " ".join(sentences[:2]).strip()
    if not short_summary:
        short_summary = cleaned_description[:220].strip()

    if len(sentences) >= 4:
        detailed_summary = " ".join(sentences[:4]).strip()
    else:
        detailed_summary = cleaned_description

    if title.lower() not in detailed_summary.lower():
        detailed_summary = f"{title}. {detailed_summary}"

    return short_summary, detailed_summary


def fetch_rss_items(feed_name: str, feed_url: str) -> list[dict]:
    try:
        raw = http_get(feed_url)
    except urllib.error.URLError:
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []

    items = []
    seen_links = set()

    for item in root.findall(".//item"):
        title = strip_html(item.findtext("title"))
        link = strip_html(item.findtext("link"))
        if not title or not link or link in seen_links:
            continue
        seen_links.add(link)
        description = strip_html(item.findtext("description"))
        summary, detailed_summary = build_summaries(title, description, feed_name)
        items.append(
            {
                "source": feed_name,
                "title": title,
                "link": link,
                "published": parse_feed_timestamp(item.findtext("pubDate")),
                "summary": summary,
                "detailed_summary": detailed_summary,
            }
        )

    return items


def merge_feeds(feed_group: list[dict]) -> list[dict]:
    merged = []
    for feed in feed_group:
        merged.extend(fetch_rss_items(feed["name"], feed["url"]))

    merged.sort(key=lambda item: item.get("published") or "", reverse=True)
    return merged[:MAX_NEWS_ITEMS]


def fetch_nifty500_symbols() -> list[dict]:
    for url in NIFTY_500_URLS:
        try:
            decoded = http_get(url).decode("utf-8", errors="ignore")
        except urllib.error.URLError:
            continue

        reader = csv.DictReader(decoded.splitlines())
        symbols = []

        for row in reader:
            symbol = (row.get("Symbol") or row.get("symbol") or "").strip()
            name = (row.get("Company Name") or row.get("Company") or symbol).strip()
            industry = (row.get("Industry") or row.get("industry") or "Unspecified").strip()
            if not symbol:
                continue
            symbols.append(
                {
                    "symbol": f"{symbol}.NS" if not symbol.endswith(".NS") else symbol,
                    "name": name,
                    "sector": industry,
                }
            )

        if symbols:
            return symbols

    return load_json(SEED_SYMBOLS_PATH)


def batched(items: list[dict], size: int) -> list[list[dict]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def fetch_yahoo_quotes(symbols: list[dict]) -> list[dict]:
    all_quotes = []

    for batch in batched(symbols, 75):
        joined = ",".join(item["symbol"] for item in batch)
        params = urllib.parse.urlencode({"symbols": joined})
        url = f"https://query1.finance.yahoo.com/v7/finance/quote?{params}"

        try:
            payload = json.loads(http_get(url).decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError):
            continue

        results = payload.get("quoteResponse", {}).get("result", [])
        quote_index = {quote.get("symbol"): quote for quote in results}

        for item in batch:
            quote = quote_index.get(item["symbol"])
            if not quote:
                continue
            price = quote.get("regularMarketPrice")
            change_percent = quote.get("regularMarketChangePercent")
            if price is None or change_percent is None:
                continue

            all_quotes.append(
                {
                    "symbol": item["symbol"],
                    "name": quote.get("longName") or item["name"],
                    "price": price,
                    "change_percent": change_percent,
                    "market_cap": quote.get("marketCap") or 0,
                    "currency": quote.get("currency") or "INR",
                    "sector": item.get("sector") or "Unspecified",
                    "volume": quote.get("regularMarketVolume") or 0,
                }
            )

    return all_quotes


def derive_trade_signals(trade_items: list[dict], stock_quotes: list[dict]) -> list[str]:
    titles = " ".join(item["title"].lower() for item in trade_items)

    themes = []
    keyword_map = {
        "shipping": "Shipping and logistics stories are moving, suggesting fresh supply-chain watchpoints.",
        "customs": "Customs and tariff updates are appearing in the latest India trade coverage.",
        "export": "Export-oriented signals are active across the current headline set.",
        "import": "Import-cost and sourcing themes are visible in the latest snapshot.",
        "rupee": "Currency-linked trade commentary is showing up, which can affect landed costs and margins."
    }

    for keyword, message in keyword_map.items():
        if keyword in titles:
            themes.append(message)

    if stock_quotes:
        positive = sum(1 for quote in stock_quotes if quote["change_percent"] > 0)
        negative = sum(1 for quote in stock_quotes if quote["change_percent"] < 0)
        if positive > negative:
            themes.append("The stock watchlist is tilting positive in the latest market snapshot.")
        elif negative > positive:
            themes.append("The stock watchlist is tilting risk-off in the latest market snapshot.")

    if not themes:
        themes.append("The dashboard is running, but the latest mix is balanced enough that no single trade theme dominates.")

    return themes[:5]


def summarize_stocks(quotes: list[dict], coverage_count: int) -> dict:
    sorted_by_change = sorted(quotes, key=lambda item: item["change_percent"], reverse=True)
    sorted_by_volume = sorted(quotes, key=lambda item: item["volume"], reverse=True)

    return {
        "meta": {
            "coverage_label": f"{coverage_count} Indian stock symbols scanned",
            "note": "If the NSE constituent file is reachable, the workflow scales toward Nifty 500 coverage automatically."
        },
        "top_gainers": sorted_by_change[:6],
        "top_losers": list(reversed(sorted_by_change[-6:])),
        "most_active": sorted_by_volume[:6],
        "watchlist": sorted_by_change[:WATCHLIST_LIMIT]
    }


def main():
    feeds = load_json(FEEDS_PATH)
    fallback_data = load_json(DATA_PATH)
    trade_items = merge_feeds(feeds["trade_news"]) or fallback_data["sections"]["trade_news"]["items"]
    india_items = merge_feeds(feeds["india_business"]) or fallback_data["sections"]["india_business"]["items"]
    global_items = merge_feeds(feeds["global_business"]) or fallback_data["sections"]["global_business"]["items"]

    symbols = fetch_nifty500_symbols()
    quotes = fetch_yahoo_quotes(symbols)
    stocks = summarize_stocks(quotes, len(symbols)) if quotes else fallback_data["sections"]["stocks"]

    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "metrics": {
            "total_headlines": len(trade_items) + len(india_items) + len(global_items),
            "stock_symbols_covered": len(symbols)
        },
        "sections": {
            "trade_signals": derive_trade_signals(trade_items, quotes),
            "trade_news": {"items": trade_items},
            "india_business": {"items": india_items},
            "global_business": {"items": global_items},
            "stocks": stocks
        }
    }

    DATA_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {DATA_PATH}")


if __name__ == "__main__":
    main()
