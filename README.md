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
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # macOS/Linux
```
All commands use the venv python explicitly so sub-agents work without activation.

## The data tool

```bash
.venv/Scripts/python tools/dse.py prices --limit 20 --sort value   # whole-market snapshot
.venv/Scripts/python tools/dse.py quote GP SQURPHARMA BEXIMCO       # specific tickers
.venv/Scripts/python tools/dse.py company GP                         # fundamentals
.venv/Scripts/python tools/dse.py index                              # breadth, top gainers/losers
.venv/Scripts/python tools/dse.py portfolio data/portfolio.csv       # your live P&L
```

## Your portfolio

Edit `data/portfolio.csv`:

```csv
code,quantity,buy_price
GP,100,260.00
SQURPHARMA,200,210.50
```

## Daily PDF report

```bash
.venv/Scripts/python tools/report.py --buy 6 --watch 6
```

Scans **all** DSE shares and writes a dated report to
`reports/DSE_Analysis_YYYY-MM-DD_HHMM_BDT.pdf` containing:

- **Market snapshot** — regime (bullish/bearish/mixed), advances/declines, value traded.
- **Buy candidates** — momentum names on volume, each with P/E, dividend yield, category,
  and an entry / stop / target plan. Flags `HIGH P/E` and weak `Cat B/N/Z`.
- **Watchlist** — overbought spikes & volume dips to wait on, with entry conditions.
- **Avoid / risk** — real crashers (near lower circuit) + illiquid shells.

## Accuracy engine

The screener can use stored OHLC history in `data/dse.db` for technical indicators,
chart-pattern reads, composite scoring, and walk-forward backtest validation.

Backfill once:

```bash
.venv/Scripts/python tools/history.py --all --start 2023-01-01
```

Refresh daily after EOD:

```bash
.venv/Scripts/python tools/refresh.py
```

This captures the latest live snapshot into SQLite and writes `reports/backtest.json`,
which the PDF includes when present. The score combines trend, RSI, moving averages,
volume ratio, support/resistance, fundamentals, liquidity, and hard risk gates. It is
a quantitative aid, not a prediction.

## REST API (optional)

A thin FastAPI layer wraps the same scraper — handy if you want HTTP/JSON access
(other apps, scripts, a future UI). No database; it reuses `tools/dse.py` + `report.py`.

```bash
.venv/Scripts/uvicorn api.main:app --port 8000      # or:  ./run_api.ps1
# interactive docs:  http://localhost:8000/docs
```

Endpoints:

| Method | Path | What |
|--------|------|------|
| GET | `/api/analysis?buy=6&watch=6&cash=36600.98&investor=B10526` | **everything in one call**: market + screen + portfolio + PDF |
| GET | `/api/health` | liveness |
| GET | `/api/prices` | whole market, every share tagged |
| GET | `/api/quote?codes=GP,BEXIMCO` | specific tickers |
| GET | `/api/company?code=GP` | fundamentals |
| GET | `/api/index` | breadth + gainers/losers/most-active |
| GET | `/api/overview?buy=6&watch=6` | screened BUY / WATCH / AVOID |
| GET | `/api/portfolio` | live P&L from `data/portfolio.csv` |
| GET | `/api/report?buy=6&watch=6&cash=36600.98&investor=B10526` | build PDF → `{url}` |
| GET | `/reports/{file}` | download a generated PDF |

Additional insight endpoints:

| Method | Path | What |
|--------|------|------|
| GET | `/api/history?code=GP&days=420` | stored OHLC history |
| GET | `/api/indicators?code=GP` | SMA/RSI/volatility/ATR/trend metrics |
| GET | `/api/patterns?code=GP` | support/resistance + chart-pattern read |
| GET | `/api/score?code=GP` | composite score for one share |
| GET | `/api/score?limit=10` | ranked scored market from stored history |
| GET | `/api/backtest?horizon=20&code=GP` | walk-forward signal validation |
| POST | `/api/snapshot/capture` | capture live snapshot into SQLite |
| POST | `/api/history/backfill?code=GP&start=2023-01-01` | backfill one code |

## Telegram bot (optional)

Run a small polling bot so Telegram can trigger the same local analysis pipeline:

```powershell
copy .env.example .env
# edit .env and fill TELEGRAM_BOT_TOKEN + TELEGRAM_ALLOWED_CHAT_IDS
.\run_telegram_bot.ps1
```

Bot commands:

```text
/id
/health
/analysis
/analysis --buy 8 --watch 6 --cash 36600.98 --investor B10526
```

`/analysis` forces a fresh market fetch, builds the PDF report, sends a compact
trade brief, then uploads the generated PDF. If you host the bot on a VPS and want it
to pull the latest GitHub code before every analysis, set:

```dotenv
TELEGRAM_BOT_GIT_PULL=1
```

Keep the real `.env` local or in hosting secrets; never commit it to GitHub.

## Using the agents (inside Claude Code)

Just ask in natural language and the orchestrator routes the work, e.g.:

- *"Analyse GP for me"* → technical + fundamentals + news → Buy/Hold/Sell
- *"Review my portfolio and flag the risks"*
- *"Give me a DSE market brief"*
- *"Is SQURPHARMA expensive right now?"* → fundamentals-analyst

## Notes / limitations

- Indicators need stored history. Run `tools/history.py` once, then `tools/refresh.py`
  daily. Outputs remain educational only, NOT financial advice.
- `dsebd.org` ships an incomplete TLS chain; `dse.py` falls back to an unverified
  connection (public data only, no credentials). Set `DSE_INSECURE=0` to force strict TLS.
- Only DSE is wired up; CSE could be added the same way.
- No intraday history → indicators like RSI/MACD aren't computed unless you supply data.
