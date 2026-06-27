"""Composite conviction score with visible sub-scores and risk gates."""
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
    pct = dse._pct_change(row)
    val = row.get("value_mn") or 0
    fund = fund_score if fund_score is not None else 50
    liquidity = _liquidity_volume_score(row, ind)
    risk = _risk_score(row, ind)
    fit = _portfolio_fit_score(row)
    total = round(0.35 * tech + 0.20 * liquidity + 0.20 * fund + 0.15 * risk + 0.10 * fit)
    breakdown = list(tnotes)
    penalties = _penalties(row, ind)
    breakdown.extend(penalties)
    if val < 0.5:
        return {
            "score": total,
            "signal": "AVOID",
            "technical": tech,
            "fundamental": fund_score,
            "sub_scores": _sub_scores(tech, liquidity, fund, risk, fit),
            "breakdown": breakdown + ["illiquid (<0.5mn) - hard exit"],
        }
    if pct <= -7:
        return {
            "score": total,
            "signal": "AVOID",
            "technical": tech,
            "fundamental": fund_score,
            "sub_scores": _sub_scores(tech, liquidity, fund, risk, fit),
            "breakdown": breakdown + [f"crash {pct:.1f}% - falling knife"],
        }
    if (row.get("category") or row.get("market_category") or "").upper() == "Z":
        total = min(total, 54)
        breakdown.append("Cat Z risk cap")
    if pct >= 7:
        sig = "DO NOT CHASE"
    elif total >= 72 and ind.get("rsi14", 0) < 70:
        sig = "BUY-WATCH"
    elif total >= 62:
        sig = "ENTRY ZONE"
    elif total >= 55:
        sig = "WAIT FOR DIP"
    elif total >= 45:
        sig = "HOLD"
    elif total >= 35:
        sig = "REDUCE"
    else:
        sig = "AVOID"
    return {
        "score": int(total),
        "signal": sig,
        "technical": tech,
        "fundamental": fund_score,
        "sub_scores": _sub_scores(tech, liquidity, fund, risk, fit),
        "breakdown": breakdown,
    }


def _liquidity_volume_score(row, ind):
    val = row.get("value_mn") or 0
    if val >= 20:
        s = 85
    elif val >= 5:
        s = 70
    elif val >= 1:
        s = 50
    elif val >= 0.5:
        s = 35
    else:
        s = 15
    vr = ind.get("vol_ratio")
    if vr and vr >= 1.5:
        s += 10
    return max(0, min(100, int(round(s))))


def _risk_score(row, ind):
    s = 75
    pct = dse._pct_change(row)
    if pct >= 7:
        s -= 25
    if pct <= -7:
        s -= 30
    if (row.get("category") or row.get("market_category") or "").upper() == "Z":
        s -= 35
    pe = row.get("pe")
    if pe is not None and pe > 40:
        s -= 15
    if ind.get("sma50") and ind.get("last_close") and ind["last_close"] < ind["sma50"]:
        s -= 15
    dd = ind.get("drawdown")
    if dd is not None and dd <= -35:
        s -= 15
    if (row.get("value_mn") or 0) < 1:
        s -= 10
    return max(0, min(100, int(round(s))))


def _portfolio_fit_score(row):
    s = 60
    weight = row.get("portfolio_weight_pct")
    if weight is not None:
        if weight >= 35:
            s -= 30
        elif weight >= 20:
            s -= 15
    pressure = row.get("exit_pressure")
    if pressure is not None:
        if pressure >= 0.2:
            s -= 25
        elif pressure >= 0.05:
            s -= 10
    backtest = row.get("backtest") or {}
    win_rate = backtest.get("win_rate")
    avg_return = backtest.get("avg_return")
    if win_rate is not None and win_rate < 45:
        s -= 10
    if avg_return is not None and avg_return < 0:
        s -= 10
    return max(0, min(100, int(round(s))))


def _penalties(row, ind):
    notes = []
    pct = dse._pct_change(row)
    if pct >= 7:
        notes.append("upper circuit chase risk")
    if (row.get("value_mn") or 0) < 1:
        notes.append("low value traded")
    if (row.get("category") or row.get("market_category") or "").upper() == "Z":
        notes.append("Cat Z")
    pe = row.get("pe")
    if pe is not None and pe > 40:
        notes.append("very high P/E")
    if ind.get("sma50") and ind.get("last_close") and ind["last_close"] < ind["sma50"]:
        notes.append("below SMA50")
    dd = ind.get("drawdown")
    if dd is not None and dd <= -35:
        notes.append("major drawdown")
    if row.get("portfolio_weight_pct") is not None and row["portfolio_weight_pct"] >= 35:
        notes.append("portfolio concentration")
    return notes


def _sub_scores(technical, liquidity, fundamental, risk, portfolio_fit):
    return {
        "technical": technical,
        "liquidity_volume": liquidity,
        "fundamentals": fundamental,
        "risk": risk,
        "portfolio_fit": portfolio_fit,
    }
