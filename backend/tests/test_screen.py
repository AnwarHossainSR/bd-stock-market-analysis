from pathlib import Path

from app.services import dse, screen

FX = Path(__file__).parent / "fixtures"


def test_select_buckets(monkeypatch):
    rows = dse.parse_prices((FX / "prices.html").read_text(encoding="utf-8"))
    monkeypatch.setattr(screen.dse, "get_prices", lambda: rows)
    monkeypatch.setattr(screen, "enrich", lambda r: {**r, "pe": None, "div_yield": None,
                                                     "category": None, "sector": None, "range_52w": None})
    out = screen.select(3, 3)
    assert out["regime"] in {"BULLISH", "BEARISH", "MIXED"}
    assert out["breadth"]["total"] == len(rows)
    assert len(out["buy"]) <= 3 and len(out["watch"]) <= 3
    for r in out["buy"]:
        assert r["tag"] == "BUY-WATCH"


def test_levels_shape():
    lv = screen._levels({"ltp": 100, "high": 102, "low": 98, "range_52w": "50.0 - 130.0"})
    assert lv["target"] == 130.0
    assert lv["stop"] == round(98 * 0.95, 1)


def test_div_yield():
    y = screen._div_yield({"dividend_history": "215% 2025, 330% 2024", "face_value": 10.0}, 257.0)
    assert y and 8.0 < y < 9.0
