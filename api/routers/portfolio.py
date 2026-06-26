"""Portfolio endpoint: live P&L from data/portfolio.csv."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.core import PORTFOLIO_CSV, report

router = APIRouter(prefix="/api", tags=["portfolio"])


@router.get("/portfolio")
def portfolio():
    port = report.load_portfolio(PORTFOLIO_CSV)
    if port is None:
        raise HTTPException(404, "data/portfolio.csv not found")
    return port
