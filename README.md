# 🇧🇩 BD Share-Market Analysis Agents

A small multi-agent system (built for Claude Code) that analyses **Dhaka Stock Exchange
(DSE)** stocks and your own portfolio. There is no off-the-shelf marketplace plugin for
the Bangladesh market, so this is custom-built around a scraper for the public
`dsebd.org` website (no API key needed; data is **delayed / end-of-day**).

> ⚠️ Educational use only. Scraped data can lag or break if the site changes. **Not
> financial advice** — verify on the official DSE site before trading.

## Architecture

```
You / main Claude session  ──►  market-orchestrator  ──►  ┌─ technical-analyst
   (asks a question)                (coordinates)          ├─ fundamentals-analyst
                                                           ├─ news-sentiment-analyst
                                                           └─ portfolio-analyst
                                          │
                                          ▼
                                   tools/dse.py  ──►  dsebd.org  (live scrape)
```

- **market-orchestrator** — runs a full review and synthesises one decision.
- **technical-analyst** — price action, 52-week position, liquidity, momentum.
- **fundamentals-analyst** — P/E, EPS, NAV, dividend yield, market cap, category.
- **news-sentiment-analyst** — recent dated news & sentiment (web search).
- **portfolio-analyst** — live P&L, allocation, concentration risk.

## Setup

```bash
pip install -r requirements.txt
```

## The data tool

```bash
python tools/dse.py prices --limit 20 --sort value   # whole-market snapshot
python tools/dse.py quote GP SQURPHARMA BEXIMCO       # specific tickers
python tools/dse.py company GP                         # fundamentals
python tools/dse.py index                              # breadth, top gainers/losers
python tools/dse.py portfolio data/portfolio.csv       # your live P&L
```

## Your portfolio

Edit `data/portfolio.csv`:

```csv
code,quantity,buy_price
GP,100,260.00
SQURPHARMA,200,210.50
```

## Using the agents (inside Claude Code)

Just ask in natural language and the orchestrator routes the work, e.g.:

- *"Analyse GP for me"* → technical + fundamentals + news → Buy/Hold/Sell
- *"Review my portfolio and flag the risks"*
- *"Give me a DSE market brief"*
- *"Is SQURPHARMA expensive right now?"* → fundamentals-analyst

## Notes / limitations

- `dsebd.org` ships an incomplete TLS chain; `dse.py` falls back to an unverified
  connection (public data only, no credentials). Set `DSE_INSECURE=0` to force strict TLS.
- Only DSE is wired up; CSE could be added the same way.
- No intraday history → indicators like RSI/MACD aren't computed unless you supply data.
