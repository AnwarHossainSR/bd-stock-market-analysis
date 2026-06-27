import backtest
import store


def test_evaluate_uptrend(db):
    rows = [
        {
            "date": f"2026-01-{i:02d}",
            "code": "UP",
            "close": 100 + i,
            "high": 101 + i,
            "low": 99 + i,
            "ycp": 99 + i,
            "ltp": 100 + i,
            "volume": 1000,
            "value_mn": 50,
        }
        for i in range(1, 29)
    ]
    store.upsert_prices(rows, db)
    out = backtest.evaluate("UP", horizon=3, db_path=db)
    assert "by_signal" in out
    total = sum(v["n"] for v in out["by_signal"].values())
    assert total > 0
