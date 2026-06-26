---
description: Daily DSE analysis — scan all shares, pick buy + watchlist with conditions, write a dated PDF report.
argument-hint: "[optional TICKER to focus, e.g. GP]"
allowed-tools: Bash, Read, Task, WebSearch, WebFetch
---

Run a full **Dhaka Stock Exchange (DSE)** daily analysis. Scan ALL shares, pick a
shortlist to BUY + a WATCHLIST with entry/stop/target conditions, and write a **PDF
report**. Output in chat **always caveman mode** (full).

Optional focus: `$ARGUMENTS` — if a ticker given, also deep-dive it.

## Step 1 — generate the PDF report (the deliverable)
```
.venv/Scripts/python tools/report.py --buy 6 --watch 6
```
This scans all shares, enriches the shortlist with fundamentals, and writes
`reports/DSE_Analysis_YYYY-MM-DD_HHMM_BDT.pdf`. It prints the file path — capture it.

## Step 2 — pull the same data for the chat brief + sanity check
```
.venv/Scripts/python tools/dse.py screen --limit 8
.venv/Scripts/python tools/dse.py index
```
If `$ARGUMENTS` is a ticker: `.venv/Scripts/python tools/dse.py company $ARGUMENTS` and `... quote $ARGUMENTS`.
Use ONLY numbers these return. `null` = unavailable, say so. Never invent.

## Step 3 — (optional) news on top picks
For the top 2 BUY names (and `$ARGUMENTS` if given), dispatch `news-sentiment-analyst`
via Task to add recent dated context. Skip if user wants it fast. Add news to the chat
brief; the PDF stays data-driven.

## Step 4 — caveman chat brief (full)
Short summary, then point to the PDF:
1. **MARKET** — regime, advances/declines, value traded mn.
2. **BUY** — top 3-5 names: `CODE | +chg% | P/E | why + condition`. Flag HIGH P/E / Cat B-Z.
3. **WATCHLIST** — 2-3 names: `CODE | condition to enter`.
4. **AVOID** — 2-3 crashers/illiquid.
5. **TOP PICK** — single best risk/reward + one-line thesis, or "nothing clean today".
6. **PDF** — print the saved report path.

## Rules
- Caveman full every line. Drop articles/filler. Keep tickers + numbers exact.
- Every call traces to a real number or cited news. No guesses.
- BD micro-caps get manipulated — flag thin / Cat B-N-Z / extreme P/E as high risk.
- End: `data scraped dsebd.org, delayed/EOD. educational only, NOT financial advice. verify on DSE before trade.`
