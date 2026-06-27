from fastapi.testclient import TestClient

from api.main import app
from api.routers import session_dashboard


def _sheet():
    return {
        "market_state": "LIVE",
        "generated_at": "2026-06-28T11:00:00+06:00",
        "data_health": {"status": "OK", "rows": 1, "warnings": []},
        "market": {"regime": "MIXED", "advances": 1, "declines": 0, "unchanged": 0, "total": 1, "total_value_mn": 1},
        "top_value_movers": [],
        "top_gainers": [],
        "top_losers": [],
        "unusual_volume": [],
        "buy_watch": [{"code": "GP"}],
        "avoid_chase_warnings": [],
        "portfolio": {"summary": {"positions": 1}, "positions": [{"code": "GP"}], "danger": [], "disclaimer": "x"},
        "portfolio_danger_names": [],
        "disclaimer": "Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice.",
    }


def test_session_action_sheet_endpoint(monkeypatch):
    monkeypatch.setattr(session_dashboard.session, "get_action_sheet", lambda portfolio_path=None: _sheet())
    client = TestClient(app)

    response = client.get("/api/session/action-sheet")

    assert response.status_code == 200
    assert response.json()["market_state"] == "LIVE"


def test_intraday_capture_endpoint(monkeypatch):
    monkeypatch.setattr(session_dashboard.intraday, "capture_intraday", lambda: 3)
    client = TestClient(app)

    response = client.post("/api/intraday/capture")

    assert response.status_code == 200
    assert response.json() == {"captured": 3}
