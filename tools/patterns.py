"""Human-readable chart-pattern reads from history and indicators."""
from __future__ import annotations


def support_resistance(hist, lookback=60):
    h = hist[-lookback:]
    lows = [r["low"] for r in h if r.get("low") is not None]
    highs = [r["high"] for r in h if r.get("high") is not None]
    return (
        round(min(lows), 2) if lows else None,
        round(max(highs), 2) if highs else None,
    )


def analyze(hist, ind):
    signals, score = [], 0
    last = ind.get("last_close")
    s20 = ind.get("sma20")
    rsi = ind.get("rsi14")
    tr = ind.get("trend")
    cross = ind.get("sma_cross")
    sup, res = support_resistance(hist)

    if tr == "UP":
        signals.append("Uptrend (SMA20 > SMA50)")
        score += 2
    elif tr == "DOWN":
        signals.append("Downtrend (SMA20 < SMA50)")
        score -= 2
    else:
        signals.append("Sideways / range-bound")
    if cross == "GOLDEN":
        signals.append("Golden cross (SMA20 crossed above SMA50)")
        score += 2
    elif cross == "DEATH":
        signals.append("Death cross (SMA20 crossed below SMA50)")
        score -= 2
    if last and s20:
        signals.append(f"Price {'above' if last > s20 else 'below'} SMA20")
        score += 1 if last > s20 else -1
    if rsi is not None:
        if rsi >= 70:
            signals.append(f"RSI {rsi} - overbought")
            score -= 1
        elif rsi <= 30:
            signals.append(f"RSI {rsi} - oversold (possible bounce)")
            score += 1
        else:
            signals.append(f"RSI {rsi} - neutral")
    if res and last and last >= res * 0.99:
        signals.append(f"Testing/breaking resistance {res}")
        score += 1
    if sup and last and last <= sup * 1.01:
        signals.append(f"Near support {sup}")
    pos = ind.get("pos_52w")
    if pos is not None:
        signals.append(f"{pos}% up its 52-week range")
    bias = "BULLISH" if score >= 2 else "BEARISH" if score <= -2 else "NEUTRAL"
    summary = f"{bias.title()} setup: " + "; ".join(signals[:4]) + "."
    return {"summary": summary, "signals": signals, "support": sup, "resistance": res, "bias": bias}
