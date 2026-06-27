import health
import store


def test_check_health_flags_missing_portfolio_price(tmp_path, db):
    portfolio = tmp_path / "portfolio.csv"
    portfolio.write_text("code,quantity,buy_price\nGP,10,100\nMISSING,5,10\n", encoding="utf-8")
    prices = [{"code": "GP", "ltp": 100, "ycp": 99, "value_mn": 1}]
    store.upsert_prices(
        [{"date": "2026-06-25", "code": "GP", "open": 99, "high": 101, "low": 98, "close": 100, "ltp": 100, "ycp": 99, "volume": 1000, "value_mn": 1, "trades": 10}],
        db,
    )

    result = health.check_health(prices=prices, portfolio_path=portfolio, db_path=db)

    assert result["status"] == "WARN"
    assert result["db_latest_date"] == "2026-06-25"
    assert result["missing_portfolio_prices"] == ["MISSING"]
