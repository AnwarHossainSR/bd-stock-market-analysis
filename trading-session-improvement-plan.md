# Trading Session Improvement Plan

## Goal

Upgrade this project from an EOD/history-backed report generator into a practical
Bangladesh trading-session decision assistant for DSE market hours.

Primary use case:

- Run during DSE trading hours, currently Sunday-Thursday, 10:00 AM-2:00 PM BDT.
- Get a fast action sheet for portfolio holdings, buy-watch candidates, sell/reduce risks,
  unusual volume, market regime, and data-health warnings.
- Keep all outputs as decision support only: educational, NOT financial advice.

## Current State

The project already has:

- Live DSE scraper through `tools/dse.py`.
- SQLite EOD/history store through `tools/store.py`, `tools/history.py`, and `tools/snapshot.py`.
- Technical indicators, chart-pattern reads, fundamentals, composite score, and backtest.
- Full PDF report with charts, score, pattern summary, portfolio analytics, and cached backtest.
- FastAPI endpoints for history, indicators, patterns, score, backtest, snapshot, and backfill.

Main gap:

- It is optimized for EOD/full-report use, not quick live-session decisions.

## Guiding Principles

- Do not auto-trade.
- Do not claim predictions.
- Prefer "BUY-WATCH", "ENTRY ZONE", "WAIT", "TRIM", "REDUCE", "EXIT WATCH" over direct
  buy/sell commands.
- Always include the disclaimer:
  "Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice."
- Keep CLI and API thin over shared `tools/` logic.
- Tests must not hit the network.

## Phase 1: Trading Session Mode

Create:

```text
tools/session.py
```

Responsibilities:

- Detect Bangladesh local market state:
  - `PRE_MARKET`: before 10:00 AM
  - `LIVE`: 10:00 AM-2:00 PM
  - `POST_CLOSE`: 2:00 PM-2:10 PM
  - `EOD`: after 2:10 PM
  - `CLOSED`: Friday/Saturday or configured holiday
- Run a live market scan using `dse.get_prices()`.
- Produce a concise action sheet.

Outputs:

- Data health status.
- Market regime and breadth.
- Top value movers.
- Top gainers and losers.
- Unusual volume candidates.
- Buy-watch candidates.
- Avoid/chase warnings.
- Portfolio danger names.

Suggested CLI:

```powershell
.venv\Scripts\python tools\session.py
.venv\Scripts\python tools\session.py --json
.venv\Scripts\python tools\session.py --portfolio data\portfolio.csv
```

## Phase 2: Portfolio Action Engine

Create:

```text
tools/portfolio_actions.py
```

For each portfolio holding, compute:

- Current market value.
- Unrealized P&L amount and percent.
- Day change percent.
- Composite score and signal when history exists.
- Trend: `UP`, `DOWN`, `SIDE`.
- RSI zone.
- Price vs SMA20/SMA50.
- ATR-based trailing stop.
- Support and resistance.
- Support break risk.
- Liquidity/exit risk.
- Concentration risk.
- Estimated exit pressure:
  - position market value / average daily traded value

Signals:

- `HOLD`
- `ADD ONLY ON DIP`
- `TRIM`
- `REDUCE`
- `EXIT WATCH`
- `STOP LOSS HIT`
- `NO LIQUID EXIT`

Example output:

```text
GP | HOLD | score 71 | trend UP | above SMA20 | stop 245.2 | target 271.0
BEXIMCO | REDUCE | trend DOWN | below SMA50 | weak volume | P&L -12.4%
```

## Phase 3: Intraday Snapshot Store

Add a new SQLite table:

```sql
CREATE TABLE IF NOT EXISTS intraday_prices(
    ts TEXT,
    code TEXT,
    ltp REAL,
    high REAL,
    low REAL,
    ycp REAL,
    volume REAL,
    value_mn REAL,
    trades REAL,
    PRIMARY KEY(ts, code)
);
```

Create:

```text
tools/intraday.py
```

Functions:

- `capture_intraday(db_path=None, now=None) -> int`
- `latest_intraday(code, db_path=None) -> dict | None`
- `session_history(code, today=None, db_path=None) -> list[dict]`
- `price_velocity(code, window_minutes=30, db_path=None) -> dict`
- `unusual_volume(code, db_path=None) -> dict`

Use cases:

- "Volume already 2.4x normal by 11:30."
- "Price rising but value weak."
- "Breakout has real participation."
- "Portfolio holding is falling with volume."

## Phase 4: Better Buy/Sell Scoring

Refine scoring into visible sub-scores:

```text
Composite Score
- Technical: 35%
- Liquidity/volume: 20%
- Fundamentals: 20%
- Risk: 15%
- Portfolio fit: 10%
```

Add penalties:

- Upper circuit chase.
- Illiquid exit risk.
- Cat Z.
- Very high P/E.
- Below SMA50.
- Major drawdown.
- Low value traded.
- Portfolio concentration.
- Recent weak signal performance from backtest.

Preferred labels:

- `BUY-WATCH`
- `ENTRY ZONE`
- `WAIT FOR DIP`
- `HOLD`
- `TRIM`
- `REDUCE`
- `EXIT WATCH`
- `DO NOT CHASE`
- `AVOID`

## Phase 5: Watchlist And Alerts

Create:

```text
data/watchlist.csv
```

Example:

```csv
code,entry_below,breakout_above,stop,notes
GP,250,270,242,quality name
BRACBANK,62,68,59,bank leader
```

Create:

```text
tools/alerts.py
```

Alert types:

- Price near support.
- Breakout above resistance.
- Stop loss hit.
- Portfolio holding below SMA50.
- Volume spike.
- Upper circuit chase warning.
- Sudden crash warning.
- Liquidity warning.

Suggested CLI:

```powershell
.venv\Scripts\python tools\alerts.py
.venv\Scripts\python tools\alerts.py --json
```

Possible later integrations:

- Telegram alert.
- Email alert.
- Windows desktop notification.

## Phase 6: New Sub-Agents

Add these Claude sub-agents under:

```text
.claude/agents/
```

### session-monitor

Purpose:

- Live market scan.
- Market regime.
- Breadth.
- Top value movers.
- Unusual volume.
- Chase warnings.

### portfolio-risk-manager

Purpose:

- Focus only on current holdings.
- Flag hold/add/trim/reduce/exit-watch actions.
- Check liquidity, concentration, drawdown, stop levels, and trend breaks.

### entry-planner

Purpose:

- Convert candidates into entry zone, stop, target, and invalidation.
- Avoid blind buying after spikes.

### signal-auditor

Purpose:

- Check whether today’s signal is backed by enough historical/backtest evidence.
- Mark weak evidence clearly.

### news-catalyst-analyst

Purpose:

- Check recent dated news for top movers and portfolio names.
- Prevent buying technical spikes without catalyst awareness.

### daily-brief-writer

Purpose:

- Compose the final concise trading note:
  - Market
  - Portfolio action
  - Buy-watch
  - Sell/reduce watch
  - Avoid
  - Data-health status

## Phase 7: Better Reports

Keep:

```text
tools/report.py
```

For full EOD PDF.

Add:

```text
tools/session_report.py
```

For compact live-session PDF or Markdown.

Live report should be short:

- Page 1:
  - Market now.
  - Data health.
  - Portfolio action table.
  - Top 5 buy-watch.
  - Top 5 sell/reduce alerts.
  - Avoid/chase warnings.
- Page 2:
  - Charts only for portfolio danger names and top candidates.

Avoid long methodology pages during live trading.

## Phase 8: Dashboard API

Add endpoints:

```text
GET  /api/session/status
GET  /api/session/market
GET  /api/session/portfolio
GET  /api/session/alerts
GET  /api/session/candidates
GET  /api/session/action-sheet
POST /api/intraday/capture
```

These should reuse `tools/session.py`, `tools/intraday.py`, `tools/alerts.py`, and
`tools/portfolio_actions.py`.

## Phase 9: Data Quality Guard

Create:

```text
tools/health.py
```

Checks:

- DSE fetch success/failure.
- Number of parsed rows.
- Stale data detection.
- Zero-LTP anomaly detection.
- Cache age.
- Missing portfolio prices.
- DB latest date.
- Intraday latest timestamp.

Example output:

```text
DATA HEALTH: OK
latest scrape: 11:42 BDT
rows: 397
stale: no
warnings: 9 zero-LTP names ignored
```

## Recommended Build Order

1. `tools/session.py` trading-time mode.
2. `tools/portfolio_actions.py` portfolio action engine.
3. `tools/intraday.py` intraday snapshot table.
4. `tools/alerts.py` watchlist and alerts.
5. `tools/session_report.py` compact live report.
6. New `.claude/agents/` sub-agents.
7. API session endpoints.
8. Optional Telegram/email/desktop alerts.

## First Milestone

Build Phase 1 and Phase 2 first.

Expected result:

```powershell
.venv\Scripts\python tools\session.py
```

Returns:

- Market state.
- Data health.
- Portfolio action table.
- Top buy-watch candidates.
- Reduce/exit-watch holdings.
- Avoid/chase warnings.
- Short disclaimer.

This gives the most practical daily value during 10:00 AM-2:00 PM BDT trading.

