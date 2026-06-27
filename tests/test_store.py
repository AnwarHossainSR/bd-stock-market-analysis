import store


def test_upsert_and_history(db):
    store.init_db(db)
    rows = [
        {"date": "2026-06-24", "code": "GP", "close": 250, "ltp": 250, "high": 252, "low": 249, "ycp": 248, "volume": 1000, "value_mn": 5.0},
        {"date": "2026-06-25", "code": "GP", "close": 255, "ltp": 255, "high": 256, "low": 250, "ycp": 250, "volume": 1200, "value_mn": 6.0},
    ]
    assert store.upsert_prices(rows, db) == 2
    rows[1]["close"] = 256
    store.upsert_prices(rows, db)
    h = store.history("GP", db_path=db)
    assert [r["date"] for r in h] == ["2026-06-24", "2026-06-25"]
    assert h[-1]["close"] == 256
    assert store.last_date(db) == "2026-06-25"
