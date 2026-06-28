import portfolio_actions
import store


def _history_rows(code, start=100, n=65, value_mn=10):
    rows = []
    price = start
    for i in range(n):
        price += 1
        rows.append(
            {
                "date": f"2026-04-{i + 1:02d}",
                "code": code,
                "open": price - 1,
                "high": price + 1,
                "low": price - 2,
                "close": price,
                "ltp": price,
                "ycp": price - 1,
                "volume": 100_000 + i,
                "value_mn": value_mn,
                "trades": 100,
            }
        )
    return rows


def test_analyze_portfolio_flags_no_liquid_exit(db):
    store.upsert_prices(_history_rows("GP", value_mn=0.2), db)
    holdings = [{"code": "GP", "quantity": 10_000, "buy_price": 100}]
    prices = [{"code": "GP", "ltp": 150, "ycp": 148, "high": 152, "low": 147, "volume": 200_000, "value_mn": 0.2}]

    result = portfolio_actions.analyze_portfolio(holdings, prices, db_path=db)

    pos = result["positions"][0]
    assert pos["liquidity_risk"] == "HIGH"
    assert pos["signal"] == "NO LIQUID EXIT"
    assert result["danger"][0]["code"] == "GP"


def test_analyze_portfolio_add_only_on_dip_for_uptrend(db):
    store.upsert_prices(_history_rows("GP", value_mn=20), db)
    holdings = [{"code": "GP", "quantity": 100, "buy_price": 100}]
    prices = [{"code": "GP", "ltp": 165, "ycp": 162, "high": 166, "low": 160, "volume": 500_000, "value_mn": 25}]

    result = portfolio_actions.analyze_portfolio(holdings, prices, db_path=db)

    pos = result["positions"][0]
    assert pos["trend"] == "UP"
    assert pos["signal"] in ("ADD ONLY ON DIP", "HOLD", "TRIM")
    assert pos["market_value"] == 16500


def test_format_action_table_includes_expected_columns(db):
    holdings = [{"code": "ABC", "quantity": 100, "buy_price": 10}]
    prices = [{"code": "ABC", "ltp": 12, "ycp": 11, "high": 13, "low": 10, "volume": 1000, "value_mn": 1}]

    result = portfolio_actions.analyze_portfolio(holdings, prices, db_path=db)
    text = portfolio_actions.format_action_table(result)

    assert "ABC |" in text
    assert "P&L 20.0%" in text
