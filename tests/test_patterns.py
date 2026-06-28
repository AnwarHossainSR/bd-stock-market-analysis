import indicators as ind
import patterns


def _h(cl):
    return [{"close": c, "high": c + 1, "low": c - 1, "volume": 100} for c in cl]


def test_uptrend_bullish():
    h = _h(list(range(50, 130)))
    a = patterns.analyze(h, ind.compute(h))
    assert a["bias"] == "BULLISH"
    assert a["resistance"] is not None
    assert any("trend" in s.lower() or "sma" in s.lower() for s in a["signals"])


def test_overbought_flag():
    h = _h(list(range(1, 40)))
    a = patterns.analyze(h, ind.compute(h))
    assert any("overbought" in s.lower() for s in a["signals"])
