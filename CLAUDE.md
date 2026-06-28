# BD Share-Market Analysis — agent system

Multi-agent system for analysing **Dhaka Stock Exchange (DSE)** stocks and the user's
portfolio. Data is scraped from the public `dsebd.org` site (no API key, delayed/EOD).

## Layout
New accuracy-engine modules:
- `tools/store.py`, `tools/history.py`, `tools/snapshot.py` - SQLite OHLC store,
  archive backfill, and daily live snapshot capture.
- `tools/indicators.py`, `tools/patterns.py`, `tools/fundamentals.py`, `tools/score.py`,
  `tools/backtest.py`, `tools/charts.py` - history-backed indicators, pattern reads,
  deeper fundamentals, composite scoring, validation, and PDF chart PNGs.
- `tools/refresh.py` - daily snapshot + cached backtest JSON for report validation.

- `tools/dse.py` — data backbone (scraper CLI, JSON output). All agents call this.
- `tools/report.py` — scans all shares → PDF report (buy + watchlist + conditions).
- `api/` — thin FastAPI layer over `tools/` (no DB). Reuses dse + report; nothing duplicated.
- `reports/` — generated PDFs, named `DSE_Analysis_YYYY-MM-DD_HHMM_BDT.pdf`.
- `.claude/agents/` — sub-agents:
  - `market-orchestrator` — coordinates full reviews (delegates to the others).
  - `technical-analyst`, `fundamentals-analyst`, `news-sentiment-analyst`, `portfolio-analyst`.
- `data/portfolio.csv` — the user's holdings (`code,quantity,buy_price`).
- `data/cache/` — short-TTL HTML cache (safe to delete).

## Output style
This project **always responds in caveman mode** (full). Terse, drop articles/filler,
fragments OK, keep tickers + numbers + code exact.

## Python env
Deps live in project venv `.venv`. **Always** call `.venv/Scripts/python` (sub-agents
run non-interactive, no activation). Never bare `python`.

## The data tool (run from project root)
```
.venv/Scripts/python tools/dse.py prices --limit 20 --sort value   # market snapshot
.venv/Scripts/python tools/dse.py quote GP SQURPHARMA               # specific tickers
.venv/Scripts/python tools/dse.py company GP                         # fundamentals
.venv/Scripts/python tools/dse.py index                              # breadth, gainers/losers
.venv/Scripts/python tools/dse.py screen --limit 15                  # BUY/HOLD/WAIT/AVOID tags
.venv/Scripts/python tools/dse.py portfolio data/portfolio.csv       # live P&L + per-holding tag
.venv/Scripts/python tools/history.py --code GP --start 2023-01-01   # backfill one code
.venv/Scripts/python tools/history.py --all --start 2023-01-01       # backfill market history
.venv/Scripts/python tools/refresh.py                                # snapshot + reports/backtest.json
```

## Report generator
```
.venv/Scripts/python tools/report.py --buy 6 --watch 6   # -> reports/DSE_Analysis_*.pdf
```
Scans all shares, picks BUY + WATCHLIST with entry/stop/target + fundamentals, scores,
pattern reads, embedded price/breadth/allocation charts, and cached backtest validation.
Prints the saved PDF path.

## REST API (optional HTTP layer)
```
.venv/Scripts/uvicorn api.main:app --port 8000     # or: ./run_api.ps1   ; docs at /docs
```
All-in-one: `GET /api/analysis?buy=&watch=&cash=&investor=&pdf=true` → market + screen
(buy/watch/avoid) + portfolio P&L + PDF url in one response (mirrors the `/analysis` chain).
Granular endpoints reuse `tools/`: `GET /api/health|prices|quote?codes=|company?code=|
index|overview?buy=&watch=|portfolio`, `GET /api/report?...` (→ PDF url), `GET /reports/{file}`.
Portfolio still from `data/portfolio.csv`. Insight endpoints add history, indicators,
patterns, score, backtest, snapshot capture, and historical backfill over the SQLite store.

## /analysis command
`.claude/commands/analysis.md` → `/analysis [TICKER]`. Generates the PDF report, then
prints a caveman chat brief (market / buy / watchlist / avoid / top pick) + the PDF path.
Optionally dispatches news-sentiment-analyst on top picks.

## How to orchestrate (when acting as the main session)
- "analyse <TICKER>" → dispatch `technical-analyst` + `fundamentals-analyst` +
  `news-sentiment-analyst` in parallel, then synthesise Buy/Hold/Sell.
- "review my portfolio" → `portfolio-analyst`, then drill into worst/biggest names.
- "market brief" → `.venv/Scripts/python tools/dse.py index` + `news-sentiment-analyst`.
- For a one-shot full review, the user can invoke the `market-orchestrator` agent.

## Rules for every agent
- Never fabricate prices/figures — only use what `dse.py` returns; `null` = unavailable.
- Always state the data is delayed/scraped and that output is **educational, not
  financial advice**. Tell the user to verify on the official DSE site before trading.
- Ticker codes are DSE trading codes (e.g. GP, SQURPHARMA, BEXIMCO, ROBI, WALTONHIL).
