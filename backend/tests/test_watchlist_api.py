from fastapi.testclient import TestClient

from app.main import app
from app.services import dse

client = TestClient(app)


def test_watchlist_add_list_delete(monkeypatch):
    monkeypatch.setattr(dse, "get_prices", lambda ttl=60: [
        {"code": "BEXIMCO", "ltp": 28, "ycp": 31, "high": 28, "low": 28, "value_mn": 5, "volume": 1}
    ])
    assert client.post("/api/watchlist", json={"code": "beximco", "note": "watch dip"}).status_code == 200
    items = client.get("/api/watchlist").json()
    assert items[0]["code"] == "BEXIMCO" and items[0]["tag"]
    assert client.delete("/api/watchlist/BEXIMCO").status_code == 200
    assert client.get("/api/watchlist").json() == []
