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
- `tools/report.py` — scans all shares → Bangla PDF report (buy/watch/avoid,
  portfolio, prediction, optional Claude/Codex commentary).
- `tools/telegram_bot.py` — local Telegram polling bot. `/analysis` sends the
  rule-based PDF only; it does not call Claude/Codex or any LLM API.
- `run_telegram_bot.ps1`, `run_telegram_bot.sh` — local bot launchers.
- `api/` — thin FastAPI layer over `tools/` (no DB). Reuses dse + report; nothing duplicated.
- `reports/` — generated PDFs, named `DSE_Analysis_YYYY-MM-DD_HHMM_BDT.pdf`.
- `reports/ai_commentary_latest.md` — temporary local Claude/Codex commentary
  file used by `/analysis` before building the PDF.
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

When `/analysis` is running inside Claude/Codex, first write local AI commentary to
`reports/ai_commentary_latest.md`, then inject it into the PDF:
```
.venv/Scripts/python tools/report.py --buy 6 --watch 6 --investor B10526 --ai-commentary-file reports/ai_commentary_latest.md
```

The report generator itself must not call OpenAI, Anthropic, Ollama, or any other LLM
API. AI commentary comes only from the active Claude/Codex session and must be based on
numbers fetched by `tools/dse.py`.

## REST API (optional HTTP layer)
```
.venv/Scripts/uvicorn api.main:app --port 8000     # or: ./run_api.ps1   ; docs at /docs
```
All-in-one: `GET /api/analysis?buy=&watch=&cash=&investor=&pdf=true` → market + screen
(buy/watch/avoid) + portfolio P&L + PDF url in one response. This is rule-based and
does not include Claude/Codex commentary unless a separate local PDF command injects it.
Granular endpoints reuse `tools/`: `GET /api/health|prices|quote?codes=|company?code=|
index|overview?buy=&watch=|portfolio`, `GET /api/report?...` (→ PDF url), `GET /reports/{file}`.
Portfolio still from `data/portfolio.csv`. Insight endpoints add history, indicators,
patterns, score, backtest, snapshot capture, and historical backfill over the SQLite store.

## /analysis command
`.claude/commands/analysis.md` → `/analysis [TICKER]`.

Expected flow:
1. Run rule-engine data commands first:
   - `.venv/Scripts/python tools/dse.py screen --limit 8`
   - `.venv/Scripts/python tools/dse.py index`
   - if focused ticker: `company` + `quote`
2. Claude/Codex writes concise Bangla commentary to `reports/ai_commentary_latest.md`.
3. Run `tools/report.py --ai-commentary-file reports/ai_commentary_latest.md`.
4. Print caveman chat brief (market / buy / watchlist / avoid / top pick) + PDF path.
5. Optionally dispatch `news-sentiment-analyst` on top picks for chat context.

If `/analysis` is triggered from Telegram, skip the Claude/Codex commentary step and
send the rule-based Bangla PDF.

## Telegram bot
Use local polling only:
```
./run_telegram_bot.sh
# or PowerShell:
.\run_telegram_bot.ps1
```

Secrets live in `.env` and must never be committed. Minimum keys:
```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ALLOWED_CHAT_IDS=...
```

Useful commands:
- `/id` - returns the current chat id for `.env`.
- `/health` - confirms bot/repo status.
- `/analysis` - generates and sends the rule-based PDF report.

Telegram `/analysis` is intentionally not an AI session. It should not attempt to call
Claude/Codex. It only runs the local rule engine and PDF generator.

## AI commentary policy
- No LLM API calls from repo code.
- Claude/Codex may write `reports/ai_commentary_latest.md` only when the user is
  actively running `/analysis` inside Claude/Codex.
- Commentary must be in Bangla, with ticker symbols and technical terms allowed in English.
- Never invent prices, scores, dates, news, or holdings. Use only `tools/dse.py`,
  `data/portfolio.csv`, generated session data, and explicitly fetched/cited news.
- If data is missing, write `n/a` or say unavailable. Do not fill gaps with guesses.

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
