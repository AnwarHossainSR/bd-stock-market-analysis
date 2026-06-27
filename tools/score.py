"""Composite conviction score: technical + fundamental + liquidity risk gates."""
from __future__ import annotations

import dse


def technical_score(ind, patt):
    s, notes = 50, []
    if ind.get("trend") == "UP":
        s += 12
        notes.append("uptrend")
    elif ind.get("trend") == "DOWN":
        s -= 12
        notes.append("downtrend")
    if ind.get("sma_cross") == "GOLDEN":
        s += 8
        notes.append("golden cross")
    elif ind.get("sma_cross") == "DEATH":
        s -= 8
        notes.append("death cross")
    rsi = ind.get("rsi14")
    if rsi is not None:
        if rsi >= 75:
            s -= 8
            notes.append("overbought")
        elif rsi <= 30:
            s += 6
            notes.append("oversold")
    last, s20 = ind.get("last_close"), ind.get("sma20")
    if last and s20:
        s += 6 if last > s20 else -6
    vr = ind.get("vol_ratio")
    if vr and vr >= 1.5:
        s += 6
        notes.append(f"volume {vr}x avg")
    pos = ind.get("pos_52w")
    if pos is not None and pos >= 95:
        s -= 4
        notes.append("near 52w high")
    if patt.get("bias") == "BULLISH":
        s += 6
    elif patt.get("bias") == "BEARISH":
        s -= 6
    return max(0, min(100, int(round(s)))), notes


def composite(row, ind, patt, fund_score):
    tech, tnotes = technical_score(ind, patt)
    fund = fund_score if fund_score is not None else 50
    total = round(0.55 * tech + 0.45 * fund)
    pct = dse._pct_change(row)
    val = row.get("value_mn") or 0
    breakdown = list(tnotes)
    if val < 0.5:
        return {
            "score": total,
            "signal": "AVOID",
            "technical": tech,
            "fundamental": fund_score,
            "breakdown": breakdown + ["illiquid (<0.5mn) - hard exit"],
        }
    if pct <= -7:
        return {
            "score": total,
            "signal": "AVOID",
            "technical": tech,
            "fundamental": fund_score,
            "breakdown": breakdown + [f"crash {pct:.1f}% - falling knife"],
        }
    if (row.get("category") or row.get("market_category") or "").upper() == "Z":
        total = min(total, 54)
        breakdown.append("Cat Z risk cap")
    if pct >= 9.5:
        sig = "WATCH"
    elif total >= 68:
        sig = "BUY"
    elif total >= 55:
        sig = "WATCH"
    elif total >= 40:
        sig = "HOLD"
    else:
        sig = "AVOID"
    return {
        "score": int(total),
        "signal": sig,
        "technical": tech,
        "fundamental": fund_score,
        "breakdown": breakdown,
    }
