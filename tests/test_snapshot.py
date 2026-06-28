import dse
import snapshot
import store


def test_capture_writes_today(db, monkeypatch):
    monkeypatch.setattr(
        dse,
        "get_prices",
        lambda ttl=60: [
            {
                "code": "GP",
                "ltp": 257,
                "high": 258,
                "low": 255,
                "ycp": 256,
                "value_mn": 50,
                "volume": 1000,
                "trades": 100,
            }
        ],
    )
    n = snapshot.capture(db_path=db, today="2026-06-26")
    assert n == 1
    h = store.history("GP", db_path=db)
    assert h[-1]["close"] == 257 and h[-1]["date"] == "2026-06-26"
