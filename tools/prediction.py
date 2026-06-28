"""Rule-based short-horizon forecast scenarios using candles + indicators.

The output is a transparent scenario read, not a guaranteed forecast.
"""
from __future__ import annotations


def _round(value, ndigits=2):
    return round(value, ndigits) if value is not None else None


def _last_candle(hist: list[dict], live_row: dict | None = None) -> dict | None:
    if live_row and live_row.get("ltp") is not None and live_row.get("high") is not None and live_row.get("low") is not None:
        return {
            "open": live_row.get("ycp"),
            "high": live_row.get("high"),
            "low": live_row.get("low"),
            "close": live_row.get("ltp"),
            "volume": live_row.get("volume"),
            "value_mn": live_row.get("value_mn"),
            "proxy": True,
        }
    if hist:
        row = hist[-1]
        return {
            "open": row.get("open") or row.get("ycp") or row.get("close"),
            "high": row.get("high"),
            "low": row.get("low"),
            "close": row.get("close") or row.get("ltp"),
            "volume": row.get("volume"),
            "value_mn": row.get("value_mn"),
            "proxy": False,
        }
    return None


def candle_behavior(hist: list[dict], live_row: dict | None = None) -> dict:
    candle = _last_candle(hist, live_row)
    if not candle or None in (candle.get("open"), candle.get("high"), candle.get("low"), candle.get("close")):
        return {"label": "NO_CANDLE", "summary": "candle data unavailable", "score": 0, "proxy": False}

    op, hi, lo, close = candle["open"], candle["high"], candle["low"], candle["close"]
    rng = hi - lo
    if rng <= 0:
        return {"label": "FLAT", "summary": "flat candle / no usable range", "score": 0, "proxy": candle["proxy"]}

    body = abs(close - op)
    upper = hi - max(op, close)
    lower = min(op, close) - lo
    close_pos = (close - lo) / rng
    body_pct = body / rng
    direction = "green" if close >= op else "red"
    score = 1 if direction == "green" else -1

    if close_pos >= 0.75:
        score += 2
    elif close_pos <= 0.25:
        score -= 2
    if lower > body * 1.5 and close_pos >= 0.55:
        score += 2
    if upper > body * 1.5 and close_pos <= 0.6:
        score -= 2
    if body_pct >= 0.6 and direction == "green":
        score += 2
    elif body_pct >= 0.6 and direction == "red":
        score -= 2

    if body_pct >= 0.6 and direction == "green" and close_pos >= 0.75:
        label, summary = "STRONG_BULLISH_CLOSE", "strong green body closing near high"
    elif body_pct >= 0.6 and direction == "red" and close_pos <= 0.35:
        label, summary = "STRONG_BEARISH_CLOSE", "strong red body closing near low"
    elif lower > body * 1.5 and close_pos >= 0.55:
        label, summary = "LOWER_WICK_REJECTION", "lower wick rejection / buyers defended dip"
    elif upper > body * 1.5 and close_pos <= 0.6:
        label, summary = "UPPER_WICK_REJECTION", "upper wick rejection / sellers active near high"
    elif body_pct <= 0.2:
        label, summary = "INDECISION", "small body / indecision"
    elif direction == "green":
        label, summary = "BULLISH_CANDLE", "green candle with constructive close"
    else:
        label, summary = "BEARISH_CANDLE", "red candle with weak close"

    return {
        "label": label,
        "summary": summary,
        "score": score,
        "proxy": candle["proxy"],
        "direction": direction,
        "body_pct": _round(body_pct * 100, 1),
        "close_position_pct": _round(close_pos * 100, 1),
        "upper_wick": _round(upper),
        "lower_wick": _round(lower),
    }


def predict(row: dict, hist: list[dict] | None = None, ind: dict | None = None, patt: dict | None = None) -> dict:
    hist = hist or []
    ind = ind or {}
    patt = patt or {}
    candle = candle_behavior(hist, row)
    reasons = [f"candle: {candle['summary']}"]
    score = candle.get("score", 0)

    trend = ind.get("trend")
    if trend == "UP":
        score += 2
        reasons.append("trend UP")
    elif trend == "DOWN":
        score -= 2
        reasons.append("trend DOWN")
    elif trend == "SIDE":
        reasons.append("trend SIDE")

    rsi = ind.get("rsi14")
    if rsi is not None:
        if rsi >= 75:
            score -= 2
            reasons.append(f"RSI {rsi} overbought")
        elif rsi >= 60:
            score += 1
            reasons.append(f"RSI {rsi} bullish momentum")
        elif rsi <= 30:
            score += 1
            reasons.append(f"RSI {rsi} oversold bounce risk")
        elif rsi <= 40:
            score -= 1
            reasons.append(f"RSI {rsi} weak")

    ltp = row.get("ltp")
    if ind.get("sma20") and ltp is not None:
        if ltp >= ind["sma20"]:
            score += 1
            reasons.append("price above SMA20")
        else:
            score -= 1
            reasons.append("price below SMA20")
    if ind.get("sma50") and ltp is not None and ltp < ind["sma50"]:
        score -= 2
        reasons.append("price below SMA50")

    vol_ratio = ind.get("vol_ratio")
    value = row.get("value_mn") or 0
    if vol_ratio and vol_ratio >= 1.5:
        score += 1
        reasons.append(f"volume {vol_ratio}x average")
    elif value >= 5:
        reasons.append(f"value traded {value:.1f}mn")
    elif value < 1:
        score -= 1
        reasons.append("weak value participation")

    support = patt.get("support")
    resistance = patt.get("resistance")
    if resistance and ltp and ltp >= resistance * 0.99:
        score += 1
        reasons.append(f"testing resistance {resistance}")
    if support and ltp and ltp <= support * 1.02:
        if trend == "DOWN":
            score -= 1
        reasons.append(f"near support {support}")

    pct = row.get("pct")
    if pct is None and ltp is not None and row.get("ycp"):
        pct = (ltp - row["ycp"]) / row["ycp"] * 100
    if pct is not None and pct >= 7:
        score -= 2
        reasons.append("upper-circuit chase risk")
    elif pct is not None and pct <= -7:
        score -= 2
        reasons.append("sharp selloff / falling-knife risk")

    if score >= 6:
        label, probability = "BULLISH_CONTINUATION", 62
        confidence = "HIGH" if len(hist) >= 50 else "MEDIUM"
    elif score >= 3:
        label, probability, confidence = "BULLISH_BIAS", 56, "MEDIUM"
    elif score <= -6:
        label, probability = "BEARISH_CONTINUATION", 62
        confidence = "HIGH" if len(hist) >= 50 else "MEDIUM"
    elif score <= -3:
        label, probability, confidence = "PULLBACK_RISK", 56, "MEDIUM"
    else:
        label, probability, confidence = "RANGE / UNCERTAIN", 50, "LOW"

    if len(hist) < 30:
        confidence = "LOW"
        reasons.append("limited stored history")

    return {
        "horizon": "next 1-5 sessions",
        "label": label,
        "direction_score": score,
        "probability_pct": probability,
        "confidence": confidence,
        "candle": candle,
        "support": support,
        "resistance": resistance,
        "explanation": reasons[:7],
        "note": "Scenario forecast only; not a guaranteed prediction or financial advice.",
    }
