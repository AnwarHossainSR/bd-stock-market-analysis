from pathlib import Path

import fundamentals as fnd

FX = Path(__file__).parent / "fixtures"


def test_parse_more_gp():
    m = fnd.parse_more((FX / "company_gp.html").read_text(encoding="utf-8"), "GP")
    assert "nav" in m and "dividend_years" in m
    assert m["dividend_years"] >= 1


def test_fundamental_score_range():
    s, notes = fnd.fundamental_score(
        {
            "pe": 12.0,
            "pb": 2.0,
            "div_yield": 8.0,
            "dividend_years": 10,
            "market_category": "A",
            "eps_positive": True,
            "eps_growth": True,
        }
    )
    assert 0 <= s <= 100 and s >= 60
    assert isinstance(notes, list)
