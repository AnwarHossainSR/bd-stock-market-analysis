from fastapi.testclient import TestClient

from app.main import app
from app.services import dse

client = TestClient(app)


def test_post_then_get_portfolio(monkeypatch):
    monkeypatch.setattr(dse, "get_prices", lambda ttl=60: [
        {"code": "GP", "ltp": 260.0, "ycp": 257.0, "high": 261, "low": 256, "value_mn": 50, "volume": 1000}
    ])
    r = client.post("/api/portfolio", json={"holdings": [{"code": "GP", "quantity": 10, "buy_price": 250}]})
    assert r.status_code == 200
    data = client.get("/api/portfolio").json()
    assert data["summary"]["invested"] == 2500.0
    assert data["positions"][0]["code"] == "GP"
    assert data["positions"][0]["unrealized_pnl"] == 100.0


def test_delete_holding(monkeypatch):
    monkeypatch.setattr(dse, "get_prices", lambda ttl=60: [])
    client.post("/api/portfolio", json={"holdings": [{"code": "X", "quantity": 1, "buy_price": 1}]})
    hid = client.get("/api/portfolio").json()["positions"][0]["id"]
    assert client.delete(f"/api/portfolio/{hid}").json()["ok"] is True
    assert client.get("/api/portfolio").json()["positions"] == []
