import alerts


def test_generate_alerts_from_watchlist_and_portfolio(tmp_path, db):
    watchlist = tmp_path / "watchlist.csv"
    watchlist.write_text("code,entry_below,breakout_above,stop,notes\nGP,100,120,95,test\n", encoding="utf-8")
    portfolio = tmp_path / "portfolio.csv"
    portfolio.write_text("code,quantity,buy_price\nGP,10,110\n", encoding="utf-8")
    prices = [{"code": "GP", "ltp": 94, "ycp": 102, "high": 103, "low": 93, "volume": 1000, "value_mn": 0.2, "trades": 5}]

    result = alerts.generate_alerts(prices=prices, watchlist_path=watchlist, portfolio_path=portfolio, db_path=db)
    types = {a["type"] for a in result["alerts"]}

    assert "STOP_LOSS_HIT" in types
    assert "SUDDEN_CRASH_WARNING" in types
    assert "LIQUIDITY_WARNING" in types


def test_load_watchlist_missing_file(tmp_path):
    assert alerts.load_watchlist(tmp_path / "missing.csv") == []


def test_generate_alerts_counts_auto_watchlist(tmp_path, db):
    watchlist = tmp_path / "watchlist.csv"
    watchlist.write_text("code,entry_below,breakout_above,stop,notes\n", encoding="utf-8")
    portfolio = tmp_path / "portfolio.csv"
    portfolio.write_text("code,quantity,buy_price\n", encoding="utf-8")
    prices = [{"code": "ABC", "ltp": 51, "ycp": 50, "high": 52, "low": 49, "volume": 2000, "value_mn": 8, "trades": 20}]

    result = alerts.generate_alerts(prices=prices, watchlist_path=watchlist, portfolio_path=portfolio, db_path=db)

    assert result["watchlist_source"]["auto"] == 1
    assert result["watchlist_source"]["manual"] == 0
