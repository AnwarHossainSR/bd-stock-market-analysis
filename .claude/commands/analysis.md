---
description: Daily DSE analysis - scan all shares, let Claude/Codex write AI commentary, then write a dated PDF report.
argument-hint: "[optional TICKER to focus, e.g. GP]"
allowed-tools: Bash, Read, Task, WebSearch, WebFetch
---

Run a full **Dhaka Stock Exchange (DSE)** daily analysis. Scan ALL shares, pick a
shortlist to BUY + a WATCHLIST with entry/stop/target conditions, write a local
Claude/Codex Bangla AI commentary section, and then write the **PDF report**.
Output in chat **always caveman mode** (full).

Optional focus: `$ARGUMENTS` - if a ticker is given, also deep-dive it.

## Step 1 - pull rule-engine data first
```
.venv/Scripts/python tools/dse.py screen --limit 8
.venv/Scripts/python tools/dse.py index
```

If `$ARGUMENTS` is a ticker, also run:
```
.venv/Scripts/python tools/dse.py company $ARGUMENTS
.venv/Scripts/python tools/dse.py quote $ARGUMENTS
```

Use ONLY numbers these commands return. `null` = unavailable, say so. Never invent.

## Step 2 - write Claude/Codex AI commentary for the PDF
Based only on Step 1 outputs and explicitly fetched ticker data, write concise Bangla
trader commentary into:

```
reports/ai_commentary_latest.md
```

Required structure:
```
AI Prediction
Market View: ...
Best Setups: ...
Portfolio View: ...
Risk / Avoid: ...
Next 1-5 Sessions: ...
Action Discipline: ...
```

Rules:
- Bengali explanation; ticker symbols and technical terms may stay English.
- No invented prices, scores, dates, or news.
- No final buy/sell command; decision support only.
- Mention official DSE verification, liquidity, and news check.

## Step 3 - generate the PDF report
```
.venv/Scripts/python tools/report.py --buy 6 --watch 6 --investor B10526 --ai-commentary-file reports/ai_commentary_latest.md
```

This scans all shares, enriches the shortlist with fundamentals, includes portfolio
P&L from `data/portfolio.csv`, score/pattern reads, embedded charts, the local
Claude/Codex AI commentary, cached backtest validation when `reports/backtest.json`
exists, and a methodology page. It writes
`reports/DSE_Analysis_YYYY-MM-DD_HHMM_BDT.pdf`. It prints the file path - capture it.
Add `--cash <ledger balance>` to show Total Equity.

If stored history is available, `/api/score` and the PDF include composite score,
signal, technical/fundamental breakdown, and chart-pattern summary.

## Step 4 - optional news on top picks
For the top 2 BUY names and `$ARGUMENTS` if given, dispatch `news-sentiment-analyst`
via Task to add recent dated context. Skip if user wants it fast. Add news to the chat
brief; the PDF AI commentary must stay tied to fetched data.

## Step 5 - caveman chat brief (full)
Short summary, then point to the PDF:
1. **MARKET** - regime, advances/declines, value traded mn.
2. **BUY** - top 3-5 names: `CODE | +chg% | P/E | why + condition`. Flag HIGH P/E / Cat B-Z.
3. **WATCHLIST** - 2-3 names: `CODE | condition to enter`.
4. **AVOID** - 2-3 crashers/illiquid.
5. **TOP PICK** - single best risk/reward + one-line thesis, or "nothing clean today".
6. **PDF** - print the saved report path.

## Rules
- Caveman full every line. Drop articles/filler. Keep tickers + numbers exact.
- Every call traces to a real number or cited news. No guesses.
- BD micro-caps get manipulated - flag thin / Cat B-N-Z / extreme P/E as high risk.
- End: `data scraped dsebd.org, delayed/EOD. educational only, NOT financial advice. verify on DSE before trade.`
