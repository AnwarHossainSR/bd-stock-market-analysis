"""Live-session dashboard endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from api.core import PORTFOLIO_CSV, alerts, health, intraday, session

router = APIRouter(prefix="/api", tags=["session"])


@router.get("/session/status")
def session_status():
    sheet = session.get_action_sheet(portfolio_path=PORTFOLIO_CSV)
    return {
        "market_state": sheet["market_state"],
        "generated_at": sheet["generated_at"],
        "data_health": sheet["data_health"],
        "disclaimer": sheet["disclaimer"],
    }


@router.get("/session/market")
def session_market():
    sheet = session.get_action_sheet(portfolio_path=PORTFOLIO_CSV)
    return {
        "market_state": sheet["market_state"],
        "market": sheet["market"],
        "top_value_movers": sheet["top_value_movers"],
        "top_gainers": sheet["top_gainers"],
        "top_losers": sheet["top_losers"],
        "unusual_volume": sheet["unusual_volume"],
        "disclaimer": sheet["disclaimer"],
    }


@router.get("/session/portfolio")
def session_portfolio():
    sheet = session.get_action_sheet(portfolio_path=PORTFOLIO_CSV)
    return sheet.get("portfolio") or {"summary": {"positions": 0}, "positions": [], "danger": [], "disclaimer": sheet["disclaimer"]}


@router.get("/session/alerts")
def session_alerts():
    return alerts.generate_alerts(portfolio_path=PORTFOLIO_CSV)


@router.get("/session/candidates")
def session_candidates():
    sheet = session.get_action_sheet(portfolio_path=PORTFOLIO_CSV)
    return {
        "buy_watch": sheet["buy_watch"],
        "avoid_chase_warnings": sheet["avoid_chase_warnings"],
        "unusual_volume": sheet["unusual_volume"],
        "disclaimer": sheet["disclaimer"],
    }


@router.get("/session/action-sheet")
def session_action_sheet():
    return session.get_action_sheet(portfolio_path=PORTFOLIO_CSV)


@router.get("/session/health")
def session_health():
    return health.check_health(portfolio_path=PORTFOLIO_CSV)


@router.post("/intraday/capture")
def capture_intraday():
    return {"captured": intraday.capture_intraday()}
