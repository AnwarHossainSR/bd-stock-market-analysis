from datetime import datetime
import os

import report


def test_build_pdf_with_history(monkeypatch, tmp_path):
    hist = [
        {
            "date": f"d{i}",
            "close": 100 + i,
            "high": 101 + i,
            "low": 99 + i,
            "ycp": 99 + i,
            "ltp": 100 + i,
            "volume": 100,
            "value_mn": 50,
        }
        for i in range(60)
    ]
    monkeypatch.setattr(
        report,
        "select",
        lambda b, w: {
            "regime": "BULLISH",
            "breadth": {"adv": 2, "dec": 1, "total": 3, "value_mn": 10.0},
            "buy": [
                {
                    "code": "UP",
                    "ltp": 160,
                    "pct": 1.0,
                    "value_mn": 50,
                    "reason": "x",
                    "pe": 10,
                    "div_yield": 5,
                    "category": "A",
                    "sector": "Bank",
                    "range_52w": "100 - 160",
                    "levels": {"support": 99, "resistance": 161, "stop": 94, "target": 170},
                    "score": 72,
                    "signal": "BUY",
                    "technical": 70,
                    "fundamental": 75,
                    "pattern_summary": "Bullish: uptrend; golden cross.",
                    "indicators": {"trend": "UP"},
                    "history": hist,
                }
            ],
            "watch": [],
            "avoid": [],
        },
    )
    monkeypatch.setattr(report, "load_portfolio", lambda p: None)
    monkeypatch.setattr(report, "REPORTS_DIR", str(tmp_path))
    p = report.build_pdf(report.select(6, 6), None, datetime(2026, 6, 26, 17, 0))
    assert p.endswith(".pdf")
    assert os.path.getsize(p) > 5000
