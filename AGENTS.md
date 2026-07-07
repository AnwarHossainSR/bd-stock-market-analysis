# Codex Instructions

This repo has a local Codex skill at `.codex/skills/dse-analysis`.

When the user types `/analysis`, `run analysis`, `use dse-analysis`, or asks for a DSE
daily report, use that skill workflow:

1. Run `.venv/Scripts/python tools/dse.py screen --limit 8`.
2. Run `.venv/Scripts/python tools/dse.py index`.
3. Write Codex Bangla commentary to `reports/ai_commentary_latest.md`.
4. Run `.venv/Scripts/python tools/report.py --buy 6 --watch 6 --investor B10526 --ai-commentary-file reports/ai_commentary_latest.md`.
5. Reply with market, buy/watch/avoid, portfolio, PDF path, and disclaimer.

Do not call any LLM API from repo code. Codex commentary means the active Codex session
writes local markdown, then the report generator injects that text into the PDF.

Telegram `/analysis` is different: it stays rule-based and does not use Codex commentary.
