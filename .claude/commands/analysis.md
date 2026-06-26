---
description: Daily DSE market analysis — screen all shares, tag buy/hold/wait/avoid, review portfolio, give a caveman brief.
argument-hint: "[optional TICKER to focus, e.g. GP]"
allowed-tools: Bash, Read, Task, WebSearch, WebFetch
---

Run a full **Dhaka Stock Exchange (DSE)** daily analysis. Output **always in caveman mode** (full intensity).

Focus argument (optional): `$ARGUMENTS` — if a ticker is given, deep-dive that one stock; if empty, do the whole market + portfolio.

## Step 1 — pull live data (run from project root)
```
.venv/Scripts/python tools/dse.py index
.venv/Scripts/python tools/dse.py screen --limit 15
.venv/Scripts/python tools/dse.py portfolio data/portfolio.csv
```
If `$ARGUMENTS` is a ticker, also: `.venv/Scripts/python tools/dse.py quote $ARGUMENTS` and `.venv/Scripts/python tools/dse.py company $ARGUMENTS`.
Use ONLY numbers these return. `null` = unavailable, say so. Never invent.

## Step 2 — deep-dive shortlist (parallel sub-agents)
Pick the notable names: top 3 `buy_watch`, the user's worst/biggest portfolio holdings, plus `$ARGUMENTS` if given.
Dispatch in parallel via Task:
- `fundamentals-analyst` — P/E, EPS, dividend yield, category for each shortlisted code.
- `news-sentiment-analyst` — recent dated news / why moving, for each shortlisted code.
Skip news for clearly illiquid AVOID names (waste).

## Step 3 — synthesize the brief (CAVEMAN, full)
Combine screen tags + fundamentals + news into final calls. Screen tag is price-only;
override it when fundamentals/news disagree (say why). Output sections:

1. **MARKET** — regime (bullish/bearish/mixed), advances/declines, total value traded mn.
2. **MY PORTFOLIO** — per holding one line: `CODE | P&L% | day% | CALL`. Total return%.
   CALL = BUY-MORE / HOLD / TRIM / SELL / WAIT + 3-5 word reason.
3. **BUY WATCH** — market candidates worth eyeing. `CODE | +chg% | why`. Note overbought = wait.
4. **AVOID** — crashers / illiquid / Z-category. `CODE | reason`.
5. **WAIT** — overbought spikes, don't chase today.
6. **TOP PICK** — single best risk/reward today + one-line thesis. Or "nothing clean today".

## Rules
- Caveman full every line. Drop articles/filler. Fragments OK. Keep tickers + numbers exact.
- Every call traces to a real number or a cited news item. No guesses.
- BD micro-caps get manipulated — flag thin/Z names as high risk.
- End with one line: `data scraped dsebd.org, delayed/EOD. educational only, NOT financial advice. verify on DSE before trade.`
