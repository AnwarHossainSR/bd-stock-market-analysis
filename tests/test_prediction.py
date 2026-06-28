import prediction


def test_bullish_prediction_uses_candle_and_trend():
    hist = []
    for i in range(60):
        price = 100 + i
        hist.append({"open": price - 1, "high": price + 2, "low": price - 2, "close": price + 1, "volume": 1000})
    row = {"code": "ABC", "ltp": 162, "high": 163, "low": 155, "ycp": 156, "value_mn": 10, "pct": 3}
    ind = {"trend": "UP", "rsi14": 62, "sma20": 150, "sma50": 140, "vol_ratio": 1.8}
    patt = {"support": 145, "resistance": 163}

    out = prediction.predict(row, hist, ind, patt)

    assert out["label"] in ("BULLISH_CONTINUATION", "BULLISH_BIAS")
    assert out["probability_pct"] >= 56
    assert "candle" in out["explanation"][0]


def test_upper_wick_rejection_is_pullback_risk():
    row = {"code": "ABC", "ltp": 101, "high": 110, "low": 100, "ycp": 104, "value_mn": 8, "pct": -3}
    out = prediction.predict(row, [], {"trend": "DOWN", "rsi14": 38, "sma20": 105, "sma50": 108}, {})

    assert out["label"] in ("PULLBACK_RISK", "BEARISH_CONTINUATION")
    assert out["confidence"] == "LOW"
