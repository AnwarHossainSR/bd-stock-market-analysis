from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services import dse, screen

client = TestClient(app)
FX = Path(__file__).parent / "fixtures"


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_prices_and_overview(monkeypatch):
    rows = dse.parse_prices((FX / "prices.html").read_text(encoding="utf-8"))
    monkeypatch.setattr(dse, "get_prices", lambda ttl=60: rows)
    monkeypatch.setattr(screen.dse, "get_prices", lambda: rows)
    monkeypatch.setattr(screen, "enrich", lambda r: {**r, "pe": None, "div_yield": None,
                                                     "category": None, "sector": None, "range_52w": None})
    assert client.get("/api/prices").json()["count"] == len(rows)
    ov = client.get("/api/overview?buy=2&watch=2").json()
    assert ov["regime"] in {"BULLISH", "BEARISH", "MIXED"}
    assert len(ov["buy"]) <= 2
