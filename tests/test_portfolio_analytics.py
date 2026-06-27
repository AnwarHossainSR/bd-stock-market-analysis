import report


def test_analytics():
    port = {
        "positions": [
            {"code": "A", "mval": 60000, "sector": "Textile", "quantity": 100, "div_per_share": 2.0},
            {"code": "B", "mval": 40000, "sector": "Bank", "quantity": 50, "div_per_share": 0.0},
        ],
        "market": 100000,
        "invested": 110000,
        "pnl": -10000,
        "ret": -9.09,
    }
    a = report.portfolio_analytics(port)
    assert a["top_weight"][0] == "A" and round(a["top_weight"][1]) == 60
    assert "Textile" in a["sectors"]
    assert a["dividend_income"] == 200
