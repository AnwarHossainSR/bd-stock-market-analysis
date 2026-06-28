"""Portfolio action engine for live DSE session decisions.

All signals are decision-support labels, not trading instructions.
Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import dse
import indicators
import patterns
import score
import store

DISCLAIMER = "Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice."


def _round(value, ndigits=2):
    return round(value, ndigits) if value is not None else None


def _pct_change(row: dict | None) -> float | None:
    if not row:
        return None
    ltp, ycp = row.get("ltp"), row.get("ycp")
    if ltp is None or not ycp:
        return None
    return round((ltp - ycp) / ycp * 100, 2)


def _avg(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None]
    return sum(clean) / len(clean) if clean else None


def _rsi_zone(rsi: float | None) -> str | None:
    if rsi is None:
        return None
    if rsi >= 70:
        return "OVERBOUGHT"
    if rsi <= 30:
        return "OVERSOLD"
    if rsi >= 55:
        return "BULLISH"
    if rsi <= 45:
        return "WEAK"
    return "NEUTRAL"


def _price_vs(ltp: float | None, sma_value: float | None, label: str) -> str | None:
    if ltp is None or sma_value is None:
        return None
    side = "above" if ltp >= sma_value else "below"
    return f"{side} {label}"


def load_portfolio(path: str | Path) -> list[dict]:
    """Read a holdings CSV with code, quantity, buy_price columns."""
    holdings = []
    p = Path(path)
    if not p.exists():
        return holdings
    with p.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = (row.get("code") or "").strip().upper()
            if not code:
                continue
            holdings.append(
                {
                    "code": code,
                    "quantity": float(row.get("quantity") or 0),
                    "buy_price": float(row.get("buy_price") or 0),
                }
            )
    return holdings


def _history_metrics(code: str, ltp: float | None, db_path=None) -> dict:
    hist = store.history(code, db_path=db_path)
    if not hist:
        return {
            "has_history": False,
            "indicators": {},
            "pattern": {},
            "avg_daily_value_mn": None,
            "avg_daily_volume": None,
        }

    ind = indicators.compute(hist)
    patt = patterns.analyze(hist, ind)
    avg_value = _avg([r.get("value_mn") for r in hist[-20:]])
    avg_volume = _avg([r.get("volume") for r in hist[-20:]])

    return {
        "has_history": True,
        "indicators": ind,
        "pattern": patt,
        "avg_daily_value_mn": _round(avg_value),
        "avg_daily_volume": _round(avg_volume, 0),
    }


def _trailing_stop(ltp: float | None, atr14: float | None, support: float | None) -> float | None:
    stops = []
    if ltp is not None and atr14:
        stops.append(ltp - 2 * atr14)
    if support:
        stops.append(support * 0.98)
    return _round(max(stops)) if stops else None


def _exit_pressure(market_value: float | None, avg_daily_value_mn: float | None, current_value_mn: float | None) -> float | None:
    value_mn = avg_daily_value_mn or current_value_mn
    if market_value is None or not value_mn:
        return None
    traded_value = value_mn * 1_000_000
    return round(market_value / traded_value, 4) if traded_value else None


def _liquidity_risk(exit_pressure: float | None, current_value_mn: float | None) -> str:
    if current_value_mn is not None and current_value_mn < 0.5:
        return "HIGH"
    if exit_pressure is not None and exit_pressure >= 0.2:
        return "HIGH"
    if current_value_mn is not None and current_value_mn < 2:
        return "MEDIUM"
    if exit_pressure is not None and exit_pressure >= 0.05:
        return "MEDIUM"
    return "LOW"


def _concentration_risk(market_value: float | None, total_market_value: float) -> tuple[str, float | None]:
    if market_value is None or total_market_value <= 0:
        return "UNKNOWN", None
    weight = market_value / total_market_value * 100
    if weight >= 35:
        return "HIGH", round(weight, 2)
    if weight >= 20:
        return "MEDIUM", round(weight, 2)
    return "LOW", round(weight, 2)


def _support_break_risk(ltp: float | None, support: float | None) -> str:
    if ltp is None or not support:
        return "UNKNOWN"
    if ltp < support:
        return "BROKEN"
    if ltp <= support * 1.02:
        return "NEAR"
    return "LOW"


def _signal(row: dict, reasons: list[str]) -> str:
    ltp = row.get("ltp")
    stop = row.get("atr_trailing_stop")
    trend = row.get("trend")
    rsi_zone = row.get("rsi_zone")
    pnl_pct = row.get("pnl_pct")
    day_pct = row.get("day_change_pct")
    score_signal = row.get("score_signal")

    if ltp is None:
        reasons.append("live price missing")
        return "EXIT WATCH"
    if stop is not None and ltp <= stop:
        reasons.append(f"price <= ATR/support stop {stop}")
        return "STOP LOSS HIT"
    if row.get("liquidity_risk") == "HIGH":
        reasons.append("high liquidity/exit risk")
        return "NO LIQUID EXIT"
    if row.get("support_break_risk") == "BROKEN":
        reasons.append("support broken")
        return "EXIT WATCH"
    if trend == "DOWN" and row.get("vs_sma50") == "below SMA50":
        reasons.append("downtrend and below SMA50")
        return "REDUCE"
    if score_signal == "AVOID":
        reasons.append("composite risk signal AVOID")
        return "REDUCE"
    if row.get("concentration_risk") == "HIGH":
        reasons.append("high portfolio concentration")
        return "TRIM"
    if day_pct is not None and day_pct >= 7:
        reasons.append(f"spike {day_pct}% - avoid chasing")
        return "TRIM"
    if rsi_zone == "OVERBOUGHT" and pnl_pct is not None and pnl_pct > 0:
        reasons.append("overbought with gains")
        return "TRIM"
    if trend == "UP" and score_signal in ("BUY", "WATCH", "BUY-WATCH", "ENTRY ZONE"):
        reasons.append("uptrend; add only on pullback/entry zone")
        return "ADD ONLY ON DIP"
    return "HOLD"


def analyze_position(holding: dict, price_row: dict | None, total_market_value: float, db_path=None) -> dict:
    code = holding["code"].upper()
    qty = float(holding.get("quantity") or 0)
    buy_price = float(holding.get("buy_price") or 0)
    ltp = price_row.get("ltp") if price_row else None
    cost_value = qty * buy_price
    market_value = qty * ltp if ltp is not None else None
    pnl = market_value - cost_value if market_value is not None else None
    pnl_pct = pnl / cost_value * 100 if pnl is not None and cost_value else None

    hist_metrics = _history_metrics(code, ltp, db_path=db_path)
    ind = hist_metrics["indicators"]
    patt = hist_metrics["pattern"]
    sup = patt.get("support")
    res = patt.get("resistance")
    atr_stop = _trailing_stop(ltp, ind.get("atr14"), sup)
    exit_pressure = _exit_pressure(market_value, hist_metrics["avg_daily_value_mn"], price_row.get("value_mn") if price_row else None)
    liquidity = _liquidity_risk(exit_pressure, price_row.get("value_mn") if price_row else None)
    concentration, weight = _concentration_risk(market_value, total_market_value)

    composite = None
    if price_row and hist_metrics["has_history"]:
        composite = score.composite(price_row, ind, patt, None)

    row = {
        "code": code,
        "quantity": qty,
        "buy_price": _round(buy_price),
        "ltp": _round(ltp),
        "cost_value": _round(cost_value),
        "market_value": _round(market_value),
        "unrealized_pnl": _round(pnl),
        "pnl_pct": _round(pnl_pct),
        "day_change_pct": _pct_change(price_row),
        "score": composite.get("score") if composite else None,
        "score_signal": composite.get("signal") if composite else None,
        "trend": ind.get("trend"),
        "rsi14": ind.get("rsi14"),
        "rsi_zone": _rsi_zone(ind.get("rsi14")),
        "vs_sma20": _price_vs(ltp, ind.get("sma20"), "SMA20"),
        "vs_sma50": _price_vs(ltp, ind.get("sma50"), "SMA50"),
        "atr_trailing_stop": atr_stop,
        "support": sup,
        "resistance": res,
        "support_break_risk": _support_break_risk(ltp, sup),
        "liquidity_risk": liquidity,
        "concentration_risk": concentration,
        "portfolio_weight_pct": weight,
        "avg_daily_value_mn": hist_metrics["avg_daily_value_mn"],
        "exit_pressure": exit_pressure,
        "notes": [],
    }
    row["signal"] = _signal(row, row["notes"])
    return row


def analyze_portfolio(holdings: list[dict], prices: list[dict], db_path=None) -> dict:
    by_code = {r.get("code", "").upper(): r for r in prices}
    preliminary_values = []
    for h in holdings:
        price_row = by_code.get(h["code"].upper())
        ltp = price_row.get("ltp") if price_row else None
        preliminary_values.append((h, (float(h.get("quantity") or 0) * ltp) if ltp is not None else 0))
    total_market = sum(v for _, v in preliminary_values)
    invested = sum(float(h.get("quantity") or 0) * float(h.get("buy_price") or 0) for h in holdings)

    positions = [
        analyze_position(h, by_code.get(h["code"].upper()), total_market, db_path=db_path)
        for h, _ in preliminary_values
    ]
    market_value = sum(p.get("market_value") or 0 for p in positions)
    danger = [
        p
        for p in positions
        if p["signal"] in ("REDUCE", "EXIT WATCH", "STOP LOSS HIT", "NO LIQUID EXIT") or p["support_break_risk"] == "BROKEN"
    ]
    return {
        "summary": {
            "positions": len(positions),
            "invested": _round(invested),
            "market_value": _round(market_value),
            "unrealized_pnl": _round(market_value - invested),
            "return_pct": _round((market_value - invested) / invested * 100 if invested else None),
        },
        "positions": positions,
        "danger": danger,
        "disclaimer": DISCLAIMER,
    }


def format_action_table(result: dict) -> str:
    lines = []
    for p in result.get("positions", []):
        score_text = f"score {p['score']}" if p.get("score") is not None else "score n/a"
        trend = p.get("trend") or "trend n/a"
        sma = p.get("vs_sma20") or p.get("vs_sma50") or "SMA n/a"
        stop = f"stop {p['atr_trailing_stop']}" if p.get("atr_trailing_stop") is not None else "stop n/a"
        target = f"target {p['resistance']}" if p.get("resistance") is not None else "target n/a"
        pnl = f"P&L {p['pnl_pct']}%" if p.get("pnl_pct") is not None else "P&L n/a"
        lines.append(f"{p['code']} | {p['signal']} | {score_text} | trend {trend} | {sma} | {stop} | {target} | {pnl}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Portfolio action engine for DSE holdings")
    parser.add_argument("portfolio", nargs="?", default=str(Path(__file__).resolve().parents[1] / "data" / "portfolio.csv"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    holdings = load_portfolio(args.portfolio)
    prices = dse.get_prices()
    result = analyze_portfolio(holdings, prices)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_action_table(result))
        print(DISCLAIMER)


if __name__ == "__main__":
    main()
