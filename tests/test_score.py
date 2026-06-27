import score

IND_UP = {
    "trend": "UP",
    "rsi14": 60,
    "last_close": 100,
    "sma20": 95,
    "sma50": 90,
    "sma_cross": "GOLDEN",
    "vol_ratio": 1.5,
    "pos_52w": 70,
    "drawdown": -8,
}
PATT = {"bias": "BULLISH"}


def test_strong_buy():
    r = {"value_mn": 50, "ltp": 100, "ycp": 98}
    out = score.composite(r, IND_UP, PATT, 75)
    assert out["signal"] in ("BUY", "WATCH")
    assert out["score"] >= 60


def test_illiquid_is_avoid():
    r = {"value_mn": 0.1, "ltp": 5, "ycp": 5}
    out = score.composite(r, IND_UP, PATT, 80)
    assert out["signal"] == "AVOID"


def test_crash_is_avoid():
    r = {"value_mn": 50, "ltp": 90, "ycp": 100}
    out = score.composite(r, IND_UP, PATT, 80)
    assert out["signal"] == "AVOID"
