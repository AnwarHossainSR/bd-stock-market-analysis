from fastapi.testclient import TestClient

from app.main import app
from app.services import dse

client = TestClient(app)


def test_capture_and_history(monkeypatch):
    monkeypatch.setattr(dse, "get_prices", lambda ttl=60: [
        {"code": "GP", "ltp": 260, "ycp": 257, "high": 261, "low": 256, "value_mn": 50, "volume": 1000}
    ])
    assert client.post("/api/snapshots/capture").json()["captured"] >= 1
    client.post("/api/snapshots/capture")  # idempotent same day
    hist = client.get("/api/snapshots?code=GP&days=30").json()
    assert len(hist) == 1 and hist[0]["code"] == "GP"
