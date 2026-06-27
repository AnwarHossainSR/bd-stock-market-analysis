import session_report


def test_render_markdown_compact_sheet():
    sheet = {
        "generated_at": "2026-06-28T11:00:00+06:00",
        "market_state": "LIVE",
        "data_health": {"status": "OK", "rows": 2, "warnings": []},
        "market": {"regime": "MIXED", "advances": 1, "declines": 1, "unchanged": 0, "total_value_mn": 10},
        "portfolio": {"positions": [{"code": "GP", "signal": "HOLD", "score": 70, "trend": "UP", "pnl_pct": 5, "atr_trailing_stop": 95, "resistance": 120}]},
        "portfolio_danger_names": [],
        "buy_watch": [{"code": "ABC", "ltp": 10, "pct_change": 2, "value_mn": 5}],
        "avoid_chase_warnings": [],
        "unusual_volume": [],
        "disclaimer": "Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice.",
    }

    text = session_report.render_markdown(sheet)

    assert "# DSE Live Session Brief" in text
    assert "| GP | HOLD | 70 | UP | 5 | 95 | 120 |" in text
    assert "ABC" in text
