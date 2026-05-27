#!/usr/bin/env python3
"""
Investment Digest Generator
Reads watchlist from ~/news-investment/config.json, fetches prices & news,
generates a dark-themed HTML file on the Desktop, and opens it in the browser.

Setup: see SKILL.md for first-time configuration.
"""

import json
import os
import pathlib
import datetime
import sys
import subprocess
import xml.etree.ElementTree as ET

try:
    import yfinance as yf
    import google.generativeai as genai
    import requests
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Run: pip3 install yfinance google-generativeai python-dotenv requests")
    sys.exit(1)

# ── Config ──────────────────────────────────────────────────────────────────

HOME = pathlib.Path.home()
CONFIG_PATH = HOME / "news-investment" / "config.json"
ENV_PATH    = HOME / "news-investment" / ".env"

def load_config():
    if not CONFIG_PATH.exists():
        print(f"Config not found: {CONFIG_PATH}")
        print("Run /investment-news and follow the setup prompts.")
        sys.exit(1)
    return json.loads(CONFIG_PATH.read_text())

def load_api_key():
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH)
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("GEMINI_API_KEY not set in ~/news-investment/.env")
        print("Get a free key at https://aistudio.google.com/app/apikey")
        sys.exit(1)
    return key

# ── Price fetching ───────────────────────────────────────────────────────────

def fetch_prices(tickers: list[str]) -> dict:
    """Returns {ticker: {price, change_pct, name}} for each ticker."""
    results = {}
    if not tickers:
        return results
    print(f"  Fetching {len(tickers)} tickers…", flush=True)
    try:
        data = yf.download(tickers, period="2d", interval="1d",
                           group_by="ticker", auto_adjust=True, progress=False, threads=True)
        for t in tickers:
            try:
                if len(tickers) == 1:
                    closes = data["Close"]
                else:
                    closes = data[t]["Close"]
                closes = closes.dropna()
                if len(closes) >= 2:
                    prev, curr = float(closes.iloc[-2]), float(closes.iloc[-1])
                    pct = (curr - prev) / prev * 100
                elif len(closes) == 1:
                    curr = float(closes.iloc[-1])
                    prev = curr
                    pct = 0.0
                else:
                    results[t] = {"price": None, "change_pct": None, "name": t}
                    continue
                results[t] = {"price": curr, "change_pct": pct, "name": t}
            except Exception:
                results[t] = {"price": None, "change_pct": None, "name": t}
    except Exception as e:
        print(f"  Warning: price fetch error: {e}", file=sys.stderr)
    return results

def fetch_all_prices(config: dict) -> tuple[dict, dict, dict]:
    """Returns (section_prices, index_prices) where section_prices is {section: {ticker: data}}."""
    sections = config.get("sections", {})
    indices  = config.get("indices", [])

    all_section_tickers = [t for tickers in sections.values() for t in tickers]
    section_prices_flat = fetch_prices(all_section_tickers)
    index_prices = fetch_prices(indices)

    section_prices = {}
    for section, tickers in sections.items():
        section_prices[section] = {t: section_prices_flat.get(t, {}) for t in tickers}

    return section_prices, index_prices

# ── News fetching ─────────────────────────────────────────────────────────────

def fetch_rss(url: str, max_items: int = 8) -> list[str]:
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(r.content)
        items = root.findall(".//item")[:max_items]
        headlines = []
        for item in items:
            title = item.findtext("title", "").strip()
            if title:
                headlines.append(title)
        return headlines
    except Exception:
        return []

def fetch_news(config: dict) -> list[str]:
    feeds = config.get("news_feeds", [])
    if not feeds:
        return []
    print(f"  Fetching {len(feeds)} news feeds…", flush=True)
    all_headlines = []
    for feed in feeds:
        headlines = fetch_rss(feed.get("url", ""))
        all_headlines.extend(headlines[:5])
    return all_headlines[:30]

# ── Gemini commentary ─────────────────────────────────────────────────────────

def generate_commentary(api_key: str, section_prices: dict,
                        index_prices: dict, headlines: list[str]) -> dict:
    """Returns {ticker: commentary_string} for all tickers."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash-lite")

    all_tickers = []
    for tickers in section_prices.values():
        all_tickers.extend(tickers.keys())
    all_tickers.extend(index_prices.keys())

    price_lines = []
    for section, tickers in section_prices.items():
        for t, d in tickers.items():
            if d.get("price"):
                price_lines.append(f"{t}: ${d['price']:.2f} ({d['change_pct']:+.2f}%)")
    for t, d in index_prices.items():
        if d.get("price"):
            price_lines.append(f"{t}: {d['price']:.2f} ({d['change_pct']:+.2f}%)")

    news_text = "\n".join(headlines[:15]) if headlines else "No headlines available."

    prompt = f"""You are a concise market analyst. Given these price moves and recent headlines,
write a 1-sentence explanation for each ticker's move (or "no significant move" if flat).
Keep each explanation under 20 words. Be factual.

Prices:
{chr(10).join(price_lines)}

Recent headlines:
{news_text}

Return ONLY a JSON object: {{"TICKER": "explanation", ...}}
"""
    print("  Generating AI commentary…", flush=True)
    try:
        resp = model.generate_content(prompt)
        text = resp.text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        print(f"  Warning: Gemini error: {e}", file=sys.stderr)
        return {}

# ── HTML generation ───────────────────────────────────────────────────────────

def price_html(price, pct) -> str:
    if price is None:
        return '<span class="na">N/A</span>'
    color = "#34d399" if pct >= 0 else "#f87171"
    arrow = "▲" if pct >= 0 else "▼"
    return (f'<span class="price">${price:,.2f}</span> '
            f'<span style="color:{color}">{arrow} {abs(pct):.2f}%</span>')

def index_price_html(price, pct) -> str:
    if price is None:
        return '<span class="na">N/A</span>'
    color = "#34d399" if pct >= 0 else "#f87171"
    arrow = "▲" if pct >= 0 else "▼"
    return (f'<span class="price">{price:,.2f}</span> '
            f'<span style="color:{color}">{arrow} {abs(pct):.2f}%</span>')

def render_section(section_name: str, tickers: dict, commentary: dict) -> str:
    rows = ""
    for ticker, data in tickers.items():
        note = commentary.get(ticker, "")
        ph   = price_html(data.get("price"), data.get("change_pct", 0))
        rows += f"""
        <tr>
          <td class="ticker">{ticker}</td>
          <td class="price-cell">{ph}</td>
          <td class="note">{note}</td>
        </tr>"""
    return f"""
    <div class="section">
      <h2>{section_name}</h2>
      <table><tbody>{rows}</tbody></table>
    </div>"""

def render_indices(index_prices: dict) -> str:
    if not index_prices:
        return ""
    rows = ""
    names = {"^GSPC": "S&P 500", "^IXIC": "Nasdaq", "^DJI": "Dow Jones"}
    for ticker, data in index_prices.items():
        label = names.get(ticker, ticker)
        ph    = index_price_html(data.get("price"), data.get("change_pct", 0))
        rows += f'<td class="index-cell"><div class="index-name">{label}</div><div>{ph}</div></td>'
    return f'<div class="section"><h2>Market Indices</h2><table><tr>{rows}</tr></table></div>'

def render_news(headlines: list[str], config: dict) -> str:
    if not headlines:
        return ""
    feed_names = [f.get("name", "") for f in config.get("news_feeds", [])]
    sources = " · ".join(filter(None, feed_names))
    items = "".join(f"<li>{h}</li>" for h in headlines[:20])
    return f"""
    <div class="section">
      <h2>Headlines <span class="source-tag">{sources}</span></h2>
      <ul class="news-list">{items}</ul>
    </div>"""

def build_html(section_prices: dict, index_prices: dict,
               commentary: dict, headlines: list[str], config: dict) -> str:
    now   = datetime.datetime.now()
    date_str = now.strftime("%B %d, %Y")
    time_str = now.strftime("%H:%M")

    sections_html = ""
    for section_name, tickers in section_prices.items():
        sections_html += render_section(section_name, tickers, commentary)
    sections_html += render_indices(index_prices)
    sections_html += render_news(headlines, config)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Investment Digest — {date_str}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f1117; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 24px; }}
  .header {{ margin-bottom: 32px; border-bottom: 1px solid #1e2433; padding-bottom: 16px; }}
  .header h1 {{ font-size: 1.8rem; color: #818cf8; font-weight: 700; }}
  .header .meta {{ color: #64748b; font-size: 0.85rem; margin-top: 4px; }}
  .section {{ margin-bottom: 32px; }}
  .section h2 {{ font-size: 1rem; font-weight: 600; color: #94a3b8; text-transform: uppercase;
                  letter-spacing: 0.08em; margin-bottom: 12px; padding-bottom: 6px;
                  border-bottom: 1px solid #1e2433; }}
  table {{ width: 100%; border-collapse: collapse; }}
  tr {{ border-bottom: 1px solid #1a2030; }}
  tr:last-child {{ border-bottom: none; }}
  td {{ padding: 10px 8px; vertical-align: top; }}
  .ticker {{ font-weight: 700; color: #e2e8f0; width: 90px; font-size: 0.95rem; }}
  .price-cell {{ width: 180px; }}
  .price {{ color: #e2e8f0; font-weight: 600; }}
  .note {{ color: #94a3b8; font-size: 0.85rem; }}
  .na {{ color: #4b5563; }}
  .index-cell {{ padding: 12px 16px; text-align: center; }}
  .index-name {{ font-size: 0.78rem; color: #64748b; margin-bottom: 4px; text-transform: uppercase; }}
  .source-tag {{ font-size: 0.7rem; color: #4b5563; font-weight: 400; text-transform: none;
                  letter-spacing: 0; margin-left: 8px; }}
  .news-list {{ list-style: none; }}
  .news-list li {{ padding: 7px 0; border-bottom: 1px solid #1a2030; color: #94a3b8;
                    font-size: 0.88rem; }}
  .news-list li:last-child {{ border-bottom: none; }}
  .footer {{ margin-top: 40px; color: #374151; font-size: 0.75rem; text-align: center; }}
</style>
</head>
<body>
<div class="header">
  <h1>Investment Digest</h1>
  <div class="meta">{date_str} · Generated {time_str}</div>
</div>
{sections_html}
<div class="footer">Generated by investment-news skill · Prices via yfinance · Commentary via Gemini</div>
</body>
</html>"""

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    config  = load_config()
    api_key = load_api_key()

    print("Fetching prices…", flush=True)
    section_prices, index_prices = fetch_all_prices(config)

    all_headlines = fetch_news(config)

    commentary = generate_commentary(api_key, section_prices, index_prices, all_headlines)

    print("Building HTML…", flush=True)
    html = build_html(section_prices, index_prices, commentary, all_headlines, config)

    date_str = datetime.date.today().strftime("%Y-%m-%d")
    out_path = HOME / "Desktop" / f"{date_str}_investment-digest.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"✓ Saved → {out_path}")

    subprocess.run(["open", str(out_path)], check=False)
    print("✓ Opened in browser")

if __name__ == "__main__":
    main()
