"""Technical indicators over stored OHLC history."""
from __future__ import annotations

import numpy as np


def _closes(hist):
    return [r["close"] for r in hist if r.get("close") is not None]


def sma(vals, n):
    if len(vals) < n:
        return None
    return round(float(np.mean(vals[-n:])), 4)


def rsi(vals, n=14):
    if len(vals) <= n:
        return None
    d = np.diff(np.array(vals, dtype=float))
    gain = np.where(d > 0, d, 0.0)
    loss = np.where(d < 0, -d, 0.0)
    ag = gain[:n].mean()
    al = loss[:n].mean()
    for i in range(n, len(d)):
        ag = (ag * (n - 1) + gain[i]) / n
        al = (al * (n - 1) + loss[i]) / n
    if al == 0:
        return 100.0
    rs = ag / al
    return round(float(100 - 100 / (1 + rs)), 2)


def volatility(vals, n=20):
    clean = [v for v in vals if v and v > 0]
    if len(clean) < n + 1:
        return None
    rets = np.diff(np.log(np.array(clean[-(n + 1):], dtype=float)))
    return round(float(rets.std(ddof=1) * np.sqrt(252) * 100), 2)


def atr(hist, n=14):
    if len(hist) < n + 1:
        return None
    trs = []
    for i in range(1, len(hist)):
        high = hist[i].get("high")
        low = hist[i].get("low")
        prev_close = hist[i - 1].get("close")
        if None in (high, low, prev_close):
            continue
        trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return round(float(np.mean(trs[-n:])), 4) if len(trs) >= n else None


def max_drawdown(vals):
    clean = [v for v in vals if v and v > 0]
    if len(clean) < 2:
        return None
    arr = np.array(clean, dtype=float)
    peak = np.maximum.accumulate(arr)
    return round(float(((arr - peak) / peak).min() * 100), 2)


def volume_ratio(hist, n=20):
    vols = [r["volume"] for r in hist if r.get("volume") is not None]
    if len(vols) < n + 1:
        return None
    avg = float(np.mean(vols[-(n + 1):-1]))
    return round(vols[-1] / avg, 2) if avg else None


def pos_52w(hist):
    h = hist[-252:]
    highs = [r["high"] for r in h if r.get("high") is not None]
    lows = [r["low"] for r in h if r.get("low") is not None]
    closes = [r["close"] for r in h if r.get("close") is not None]
    if not highs or not lows or not closes:
        return None
    lo, hi = min(lows), max(highs)
    if hi <= lo:
        return None
    return round((closes[-1] - lo) / (hi - lo) * 100, 1)


def _series_sma(vals, n, end=None):
    end = len(vals) if end is None else end
    if end < n:
        return None
    return float(np.mean(vals[end - n:end]))


def trend(hist):
    vals = _closes(hist)
    s20 = sma(vals, 20)
    s50 = sma(vals, 50)
    last = vals[-1] if vals else None
    if s20 is None or s50 is None or last is None:
        return None
    if s20 > s50 and last >= s20:
        return "UP"
    if s20 < s50 and last <= s20:
        return "DOWN"
    return "SIDE"


def _sma_cross(vals):
    if len(vals) < 51:
        return None
    prev20 = _series_sma(vals, 20, len(vals) - 1)
    prev50 = _series_sma(vals, 50, len(vals) - 1)
    cur20 = _series_sma(vals, 20)
    cur50 = _series_sma(vals, 50)
    if None in (prev20, prev50, cur20, cur50):
        return None
    if prev20 <= prev50 and cur20 > cur50:
        return "GOLDEN"
    if prev20 >= prev50 and cur20 < cur50:
        return "DEATH"
    return None


def compute(hist) -> dict:
    vals = _closes(hist)
    last = vals[-1] if vals else None
    return {
        "last_close": last,
        "sma20": sma(vals, 20),
        "sma50": sma(vals, 50),
        "sma200": sma(vals, 200),
        "rsi14": rsi(vals, 14),
        "vol20": volatility(vals, 20),
        "atr14": atr(hist, 14),
        "drawdown": max_drawdown(vals),
        "vol_ratio": volume_ratio(hist, 20),
        "pos_52w": pos_52w(hist),
        "trend": trend(hist),
        "sma_cross": _sma_cross(vals),
    }
