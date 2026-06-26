from pathlib import Path

from app.services import dse

FX = Path(__file__).parent / "fixtures"


def test_parse_prices_extracts_rows():
    rows = dse.parse_prices((FX / "prices.html").read_text(encoding="utf-8"))
    assert len(rows) > 100
    assert {"code", "ltp", "high", "low", "ycp", "value_mn", "volume"} <= rows[0].keys()


def test_parse_company_gp_fundamentals():
    c = dse.parse_company((FX / "company_gp.html").read_text(encoding="utf-8"), "GP")
    assert c["code"] == "GP"
    assert c["pe"] and c["pe"] > 0
    assert c["market_category"] in {"A", "B", "N", "Z"}
    assert "%" in (c["dividend_history"] or "")


def test_rate_tags_are_valid():
    tag, reason = dse._rate({"ltp": 100.0, "ycp": 95.0, "high": 101, "low": 96, "value_mn": 50})
    assert tag in {"BUY-WATCH", "WATCH-DIP", "HOLD", "WAIT", "AVOID", "NEUTRAL", "NO-DATA"}
    assert reason
