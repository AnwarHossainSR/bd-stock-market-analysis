from datetime import datetime

import intraday
import store


def test_intraday_latest_velocity_and_unusual_volume(monkeypatch, db):
    prices_a = [{"code": "GP", "ltp": 100, "high": 101, "low": 99, "ycp": 98, "volume": 1000, "value_mn": 1, "trades": 10}]
    prices_b = [{"code": "GP", "ltp": 105, "high": 106, "low": 99, "ycp": 98, "volume": 2500, "value_mn": 3, "trades": 20}]
    calls = iter([prices_a, prices_b])
    monkeypatch.setattr(intraday.dse, "get_prices", lambda: next(calls))

    for i in range(20):
        store.upsert_prices(
            [{
                "date": f"2026-05-{i + 1:02d}",
                "code": "GP",
                "open": 90,
                "high": 101,
                "low": 89,
                "close": 95,
                "ltp": 95,
                "ycp": 94,
                "volume": 1000,
                "value_mn": 1,
                "trades": 10,
            }],
            db,
        )

    assert intraday.capture_intraday(db_path=db, now=datetime.fromisoformat("2026-06-28T10:00:00+06:00")) == 1
    assert intraday.capture_intraday(db_path=db, now=datetime.fromisoformat("2026-06-28T10:30:00+06:00")) == 1

    latest = intraday.latest_intraday("GP", db_path=db)
    assert latest["ltp"] == 105
    velocity = intraday.price_velocity("GP", db_path=db)
    assert velocity["pct_change"] == 5.0
    unusual = intraday.unusual_volume("GP", db_path=db)
    assert unusual["status"] == "SPIKE"
