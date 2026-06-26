"""Shared wiring for the API: puts tools/ on the path and re-exports the
scraper (dse) + report engines so routers reuse the exact CLI logic.

Single source of truth = tools/dse.py + tools/report.py. The API is a thin
HTTP layer over them; nothing is duplicated.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import dse  # noqa: E402  (tools/dse.py)
import report  # noqa: E402  (tools/report.py)

REPORTS_DIR = os.path.join(ROOT, "reports")
PORTFOLIO_CSV = os.path.join(ROOT, "data", "portfolio.csv")

__all__ = ["dse", "report", "ROOT", "REPORTS_DIR", "PORTFOLIO_CSV"]
