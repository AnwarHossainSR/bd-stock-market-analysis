from fastapi.testclient import TestClient

from api.core import store
from api.main import app

client = TestClient(app)


def test_history_and_indicators(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "t.db")
    store.upsert_prices(
        [
            {
                "date": f"2026-01-{i:02d}",
                "code": "GP",
                "close": 100 + i,
                "high": 101 + i,
                "low": 99 + i,
                "ycp": 99 + i,
                "ltp": 100 + i,
                "volume": 100,
                "value_mn": 5,
            }
            for i in range(1, 40)
        ]
    )
    assert client.get("/api/history?code=GP").json()
    ind = client.get("/api/indicators?code=GP").json()
    assert "rsi14" in ind
