# investment-news skill

A Claude Code skill that generates a personal daily investment digest as a dark-themed HTML page.

## What it does

Fetches stock prices for your custom watchlist, generates AI commentary via Gemini, pulls news headlines from RSS feeds, and saves `~/Desktop/YYYY-MM-DD_investment-digest.html` — then opens it in the browser.

## Install

```bash
mkdir -p ~/.claude/skills/investment-news
cp SKILL.md ~/.claude/skills/investment-news/SKILL.md
cp post_to_html.py ~/news-investment/post_to_html.py
```

## First-time setup

On first run the skill will ask you:
1. What stocks/tickers to track (organized into custom sections)
2. What news sources to pull from
3. Your Gemini API key (free at https://aistudio.google.com/app/apikey)

It creates `~/news-investment/config.json` and `~/news-investment/.env` for you.

See `config.json.example` and `.env.example` for the format if you want to configure manually.

## Dependencies

```bash
pip3 install yfinance google-generativeai python-dotenv requests
```

## Usage

In Claude Code:
```
/investment-news
```
