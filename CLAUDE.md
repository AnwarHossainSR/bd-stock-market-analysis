# BD Share-Market Analysis — agent system

Multi-agent system for analysing **Dhaka Stock Exchange (DSE)** stocks and the user's
portfolio. Data is scraped from the public `dsebd.org` site (no API key, delayed/EOD).

## Layout
- `tools/dse.py` — data backbone (scraper CLI, JSON output). All agents call this.
- `.claude/agents/` — sub-agents:
  - `market-orchestrator` — coordinates full reviews (delegates to the others).
  - `technical-analyst`, `fundamentals-analyst`, `news-sentiment-analyst`, `portfolio-analyst`.
- `data/portfolio.csv` — the user's holdings (`code,quantity,buy_price`).
- `data/cache/` — short-TTL HTML cache (safe to delete).

## The data tool (run from project root)
```
python tools/dse.py prices --limit 20 --sort value   # market snapshot
python tools/dse.py quote GP SQURPHARMA               # specific tickers
python tools/dse.py company GP                         # fundamentals
python tools/dse.py index                              # breadth, gainers/losers
python tools/dse.py portfolio data/portfolio.csv       # live P&L
```

## How to orchestrate (when acting as the main session)
- "analyse <TICKER>" → dispatch `technical-analyst` + `fundamentals-analyst` +
  `news-sentiment-analyst` in parallel, then synthesise Buy/Hold/Sell.
- "review my portfolio" → `portfolio-analyst`, then drill into worst/biggest names.
- "market brief" → `python tools/dse.py index` + `news-sentiment-analyst`.
- For a one-shot full review, the user can invoke the `market-orchestrator` agent.

## Rules for every agent
- Never fabricate prices/figures — only use what `dse.py` returns; `null` = unavailable.
- Always state the data is delayed/scraped and that output is **educational, not
  financial advice**. Tell the user to verify on the official DSE site before trading.
- Ticker codes are DSE trading codes (e.g. GP, SQURPHARMA, BEXIMCO, ROBI, WALTONHIL).
