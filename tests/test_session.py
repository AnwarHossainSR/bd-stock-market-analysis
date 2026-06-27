from datetime import datetime

import session


BD = session.BD_TZ


def test_market_state_weekday_boundaries():
    assert session.market_state(datetime(2026, 6, 28, 9, 59, tzinfo=BD)) == "PRE_MARKET"
    assert session.market_state(datetime(2026, 6, 28, 10, 0, tzinfo=BD)) == "LIVE"
    assert session.market_state(datetime(2026, 6, 28, 14, 5, tzinfo=BD)) == "POST_CLOSE"
    assert session.market_state(datetime(2026, 6, 28, 14, 11, tzinfo=BD)) == "EOD"


def test_market_state_weekend_closed():
    assert session.market_state(datetime(2026, 6, 26, 11, 0, tzinfo=BD)) == "CLOSED"
    assert session.market_state(datetime(2026, 6, 27, 11, 0, tzinfo=BD)) == "CLOSED"


def test_build_action_sheet_sections_without_network(tmp_path):
    portfolio = tmp_path / "portfolio.csv"
    portfolio.write_text("code,quantity,buy_price\nGP,10,100\n", encoding="utf-8")
    rows = [
        {"code": "GP", "ltp": 110, "ycp": 100, "high": 111, "low": 100, "volume": 1000, "value_mn": 5, "trades": 10},
        {"code": "ABC", "ltp": 51, "ycp": 50, "high": 52, "low": 49, "volume": 2000, "value_mn": 8, "trades": 20},
        {"code": "XYZ", "ltp": 90, "ycp": 100, "high": 101, "low": 88, "volume": 3000, "value_mn": 3, "trades": 30},
    ]

    sheet = session.build_action_sheet(rows, portfolio_path=portfolio, now=datetime(2026, 6, 28, 11, 0, tzinfo=BD), db_path=tmp_path / "dse.db")

    assert sheet["market_state"] == "LIVE"
    assert sheet["data_health"]["status"] == "OK"
    assert sheet["market"]["advances"] == 2
    assert sheet["market"]["declines"] == 1
    assert sheet["buy_watch"][0]["code"] == "ABC"
    assert sheet["auto_watchlist"][0]["code"] == "ABC"
    assert sheet["auto_watchlist"][0]["entry_below"] == 49
    assert sheet["avoid_chase_warnings"][0]["code"] == "GP"
    assert sheet["portfolio"]["positions"][0]["code"] == "GP"
