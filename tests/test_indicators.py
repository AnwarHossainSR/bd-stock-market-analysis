import indicators as ind


def _h(closes):
    return [{"close": c, "high": c + 1, "low": c - 1, "volume": 100} for c in closes]


def test_sma():
    assert ind.sma([1, 2, 3, 4, 5], 5) == 3.0
    assert ind.sma([1, 2], 5) is None


def test_rsi_all_up_is_100():
    assert round(ind.rsi(list(range(1, 30)), 14)) == 100


def test_trend_up():
    h = _h([i for i in range(1, 80)])
    assert ind.trend(h) == "UP"


def test_compute_keys():
    h = _h([100 + (i % 5) for i in range(1, 60)])
    c = ind.compute(h)
    assert {"sma20", "rsi14", "trend", "pos_52w", "vol_ratio"} <= c.keys()
