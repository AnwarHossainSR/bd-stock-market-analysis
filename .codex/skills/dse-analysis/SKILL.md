---
name: dse-analysis
description: Run the local Dhaka Stock Exchange analysis workflow in this repo. Use when the user types /analysis in Codex, asks to run DSE analysis, generate the daily market PDF, analyze portfolio/watch/buy/avoid lists, or add Codex AI prediction commentary to the PDF without calling any LLM API.
---

# DSE Analysis

Use this skill only from the `market-analysis` repo root. It mirrors the Claude
`/analysis` workflow for Codex.

## Core Rules

- Always use `.venv/Scripts/python`, not bare `python`.
- Do not call OpenAI, Anthropic, Ollama, or any other LLM API from repo code.
- Use Codex itself for AI commentary only when the user runs analysis inside Codex.
- Telegram `/analysis` stays rule-based only.
- Never invent prices, scores, dates, holdings, or news.
- Use only data returned by local commands, `data/portfolio.csv`, and explicitly fetched/cited news.
- Keep ticker symbols and numeric values exact.
- State that DSE data is scraped/delayed/EOD, educational only, NOT financial advice.

## Codex `/analysis` Workflow

When the user types `/analysis` or asks to run analysis from Codex:

1. Pull rule-engine data first:

```powershell
.venv/Scripts/python tools/dse.py screen --limit 8
.venv/Scripts/python tools/dse.py index
```

If the user gives a ticker, also run:

```powershell
.venv/Scripts/python tools/dse.py company TICKER
.venv/Scripts/python tools/dse.py quote TICKER
```

2. Write concise Bangla Codex commentary to:

```text
reports/ai_commentary_latest.md
```

Required structure:

```text
AI Prediction
Market View: ...
Best Setups: ...
Portfolio View: ...
Risk / Avoid: ...
Next 1-5 Sessions: ...
Action Discipline: ...
```

Commentary rules:

- Bangla explanation; ticker symbols and technical terms may stay English.
- Use only values from the commands above and any explicit ticker/news checks.
- If data is missing, write `n/a` or say unavailable.
- No final buy/sell command. Decision support only.
- Mention liquidity, news check, support/resistance, and official DSE verification.

3. Generate the Bangla PDF with commentary:

```powershell
.venv/Scripts/python tools/report.py --buy 6 --watch 6 --investor B10526 --ai-commentary-file reports/ai_commentary_latest.md
```

Add `--cash <amount>` only if the user gives a cash balance.

4. Reply with a short trader brief:

- Market regime, advances/declines, value traded.
- Top buy candidates, if any.
- Watchlist conditions, if any.
- Avoid/risk names.
- Portfolio concerns.
- PDF path.
- Disclaimer.

## Rule-Based PDF Only

For Telegram, scheduled jobs, or when Codex is not actively producing commentary, run:

```powershell
.venv/Scripts/python tools/report.py --buy 6 --watch 6 --investor B10526
```

This creates the PDF from scraper/rule data only.

## Useful Checks

Portfolio:

```powershell
.venv/Scripts/python tools/dse.py portfolio data/portfolio.csv
```

Market snapshot:

```powershell
.venv/Scripts/python tools/dse.py prices --limit 20 --sort value
```

Health:

```powershell
.venv/Scripts/python tools/dse.py index
```
