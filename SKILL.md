---
name: investment-news
description: Generate a daily investment digest as an HTML page on the Desktop. Use when the user invokes /investment-news or asks to run/generate/show the investment news or stock digest. Checks for a user-configured watchlist, asks the user to set one up if missing, then fetches prices, generates AI commentary, and saves a dark-themed HTML file to ~/Desktop/YYYY-MM-DD_investment-digest.html and opens it in the browser.
---

# Investment News Skill

Generates a personal daily investment digest — stock prices, AI-powered move explanations, and news headlines across the user's custom watchlist.

---

## Step 0 — Check setup

Check if `~/news-investment/config.json` exists:

```bash
test -f "$HOME/news-investment/config.json" && echo "found" || echo "missing"
```

Also check for the GEMINI_API_KEY:
```bash
test -f "$HOME/news-investment/.env" && grep -q "GEMINI_API_KEY" "$HOME/news-investment/.env" && echo "key found" || echo "key missing"
```

**If either is missing → run Setup (Step 1). Otherwise skip to Step 2.**

---

## Step 1 — First-time setup

### 1a — Ask for watchlist

Ask the user:
> "What stocks do you want in your investment digest? You can organize them into sections.
>
> For example:
> - **AI & Tech**: NVDA, MSFT, GOOGL
> - **US Stocks**: AAPL, TSLA, AMZN
> - **Local/Regional**: (tickers from your local exchange, e.g. SET, SGX, etc.)
> - **Indices** (optional): ^GSPC (S&P 500), ^IXIC (Nasdaq), ^DJI (Dow)
>
> Just list your tickers and I'll set everything up."

Wait for the user's response. Accept any grouping they provide. Use sensible defaults if they just give a flat list (put all in one section named "My Stocks").

### 1b — Ask for news sources (optional)

Ask:
> "Any specific news sources you want to pull headlines from? Defaults: Reuters, BBC World, CNBC. Add any RSS feed URL or news site you prefer."

### 1c — Ask for Gemini API key

If `.env` is missing:
> "I need a Gemini API key for AI commentary. Get one free at https://aistudio.google.com/app/apikey — then paste it here."

### 1d — Create config

```bash
mkdir -p "$HOME/news-investment"
```

Write `~/news-investment/config.json` with the user's watchlist:
```json
{
  "sections": {
    "AI & Tech": ["NVDA", "MSFT", "GOOGL"],
    "US Stocks": ["AAPL", "TSLA"]
  },
  "indices": ["^GSPC", "^IXIC", "^DJI"],
  "news_feeds": [
    {"name": "Reuters", "url": "https://feeds.reuters.com/reuters/businessNews"},
    {"name": "BBC World", "url": "http://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "CNBC", "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html"}
  ]
}
```

Write `~/news-investment/.env`:
```
GEMINI_API_KEY=<their key>
```

### 1e — Copy the script and install dependencies

Copy `post_to_html.py` from the skill repo to `~/news-investment/post_to_html.py`.

Install dependencies:
```bash
/opt/anaconda3/bin/pip install yfinance google-generativeai python-dotenv requests 2>&1 | tail -5
# If anaconda not found, fall back to:
pip3 install yfinance google-generativeai python-dotenv requests 2>&1 | tail -5
```

Confirm setup is complete.

---

## Step 2 — Run the digest

```bash
/opt/anaconda3/bin/python3 "$HOME/news-investment/post_to_html.py"
# If anaconda not found:
python3 "$HOME/news-investment/post_to_html.py"
```

The script takes ~30–60 seconds and prints progress:
```
Fetching prices…
Generating AI commentary…
Fetching news feeds…
Building HTML…
✓ Saved → /Users/<you>/Desktop/YYYY-MM-DD_investment-digest.html
✓ Opened in browser
```

---

## Step 3 — After running

- Tell the user the digest was saved and opened in the browser.
- File is at `~/Desktop/YYYY-MM-DD_investment-digest.html`.
- If there's an error, show the exact error message and check:
  - `~/news-investment/.env` has a valid `GEMINI_API_KEY`
  - `~/news-investment/config.json` exists and has at least one ticker
  - Dependencies: `pip3 install yfinance google-generativeai python-dotenv requests`

---

## Updating your watchlist

To change tickers later: edit `~/news-investment/config.json` directly, or say "update my watchlist" and the skill will prompt you for changes.

```bash
# Add a ticker to an existing section:
python3 -c "
import json, pathlib
p = pathlib.Path.home() / 'news-investment/config.json'
c = json.loads(p.read_text())
c['sections']['AI & Tech'].append('NEW_TICKER')
p.write_text(json.dumps(c, indent=2))
print('Updated')
"
```
