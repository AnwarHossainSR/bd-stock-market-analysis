"""Watchlist, portfolio, volume, and risk alerts for DSE session scans."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import dse
import indicators
import intraday
import patterns
import portfolio_actions
import session
import store

DISCLAIMER = "Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice."
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WATCHLIST = ROOT / "data" / "watchlist.csv"
DEFAULT_PORTFOLIO = ROOT / "data" / "portfolio.csv"


def _num(value):
    if value in (None, ""):
        return None
    return float(value)


def _pct_change(row: dict | None):
    if not row:
        return None
    ltp, ycp = row.get("ltp"), row.get("ycp")
    if ltp is None or not ycp:
        return None
    return round((ltp - ycp) / ycp * 100, 2)


def _alert(alert_type, code, message, severity="INFO", **extra):
    return {"type": alert_type, "severity": severity, "code": code, "message": message, **extra}


def load_watchlist(path: str | Path = DEFAULT_WATCHLIST) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    with p.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = (row.get("code") or "").strip().upper()
            if not code:
                continue
            out.append(
                {
                    "code": code,
                    "entry_below": _num(row.get("entry_below")),
                    "breakout_above": _num(row.get("breakout_above")),
                    "stop": _num(row.get("stop")),
                    "notes": row.get("notes") or "",
                }
            )
    return out


def _history_context(code: str, db_path=None) -> tuple[dict, dict]:
    hist = store.history(code, db_path=db_path)
    if not hist:
        return {}, {}
    ind = indicators.compute(hist)
    return ind, patterns.analyze(hist, ind)


def _volume_ratio(code: str, row: dict, db_path=None):
    uv = intraday.unusual_volume(code, db_path=db_path)
    if uv.get("volume_ratio") is not None:
        return uv["volume_ratio"]
    hist = store.history(code, days=25, db_path=db_path)
    vols = [r.get("volume") for r in hist[-20:] if r.get("volume") is not None]
    avg = sum(vols) / len(vols) if vols else None
    if avg and row.get("volume") is not None:
        return round(row["volume"] / avg, 2)
    return None


def generate_alerts(
    prices: list[dict] | None = None,
    watchlist_path: str | Path = DEFAULT_WATCHLIST,
    portfolio_path: str | Path = DEFAULT_PORTFOLIO,
    include_auto_watchlist: bool = True,
    db_path=None,
) -> dict:
    rows = prices if prices is not None else dse.get_prices()
    by_code = {r.get("code", "").upper(): r for r in rows}
    manual_watchlist = load_watchlist(watchlist_path)
    auto_watchlist = session.auto_watchlist_rows(rows, db_path=db_path) if include_auto_watchlist else []
    merged = {w["code"]: w for w in auto_watchlist}
    merged.update({w["code"]: w for w in manual_watchlist})
    watchlist = list(merged.values())
    holdings = portfolio_actions.load_portfolio(portfolio_path)
    holding_codes = {h["code"] for h in holdings}
    universe = sorted({w["code"] for w in watchlist} | holding_codes)
    alerts = []

    for item in watchlist:
        row = by_code.get(item["code"])
        if not row:
            alerts.append(_alert("MISSING_PRICE", item["code"], "watchlist name missing from latest DSE rows", "WARN"))
            continue
        ltp = row.get("ltp")
        pct = _pct_change(row)
        if item.get("entry_below") and ltp is not None and ltp <= item["entry_below"] * 1.01:
            alerts.append(_alert("PRICE_NEAR_SUPPORT", item["code"], f"LTP {ltp} near entry/support {item['entry_below']}", "INFO", ltp=ltp))
        if item.get("breakout_above") and ltp is not None and ltp >= item["breakout_above"]:
            alerts.append(_alert("BREAKOUT_ABOVE_RESISTANCE", item["code"], f"LTP {ltp} above breakout {item['breakout_above']}", "INFO", ltp=ltp))
        if item.get("stop") and ltp is not None and ltp <= item["stop"]:
            alerts.append(_alert("STOP_LOSS_HIT", item["code"], f"LTP {ltp} <= stop {item['stop']}", "HIGH", ltp=ltp))
        if pct is not None and pct >= 7:
            alerts.append(_alert("UPPER_CIRCUIT_CHASE_WARNING", item["code"], f"{pct:+.2f}% spike; do not chase", "WARN", pct_change=pct))

    for code in universe:
        row = by_code.get(code)
        if not row:
            continue
        pct = _pct_change(row)
        value_mn = row.get("value_mn") or 0
        if pct is not None and pct <= -7:
            alerts.append(_alert("SUDDEN_CRASH_WARNING", code, f"{pct:+.2f}% drop; wait for stabilization", "HIGH", pct_change=pct))
        if value_mn < 0.5 and row.get("ltp") is not None:
            alerts.append(_alert("LIQUIDITY_WARNING", code, f"thin traded value {value_mn:.2f}mn", "WARN", value_mn=value_mn))
        vr = _volume_ratio(code, row, db_path=db_path)
        if vr is not None and vr >= 1.8:
            alerts.append(_alert("VOLUME_SPIKE", code, f"volume {vr}x recent average", "INFO", volume_ratio=vr))

        if code in holding_codes:
            ind, patt = _history_context(code, db_path=db_path)
            ltp = row.get("ltp")
            if ind.get("sma50") and ltp is not None and ltp < ind["sma50"]:
                alerts.append(_alert("PORTFOLIO_BELOW_SMA50", code, f"LTP {ltp} below SMA50 {ind['sma50']}", "WARN", ltp=ltp, sma50=ind["sma50"]))
            support = patt.get("support")
            if support and ltp is not None and ltp <= support * 1.02:
                alerts.append(_alert("PRICE_NEAR_SUPPORT", code, f"LTP {ltp} near support {support}", "INFO", ltp=ltp, support=support))

    severity_rank = {"HIGH": 0, "WARN": 1, "INFO": 2}
    alerts.sort(key=lambda a: (severity_rank.get(a["severity"], 9), a["code"], a["type"]))
    return {
        "count": len(alerts),
        "watchlist_source": {
            "auto": len(auto_watchlist),
            "manual": len(manual_watchlist),
            "merged": len(watchlist),
        },
        "alerts": alerts,
        "disclaimer": DISCLAIMER,
    }


def format_alerts(result: dict) -> str:
    lines = ["DSE SESSION ALERTS"]
    if not result.get("alerts"):
        lines.append("No alerts.")
    for alert in result.get("alerts", []):
        lines.append(f"{alert['severity']} | {alert['code']} | {alert['type']} | {alert['message']}")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="DSE watchlist and portfolio alerts")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--watchlist", default=str(DEFAULT_WATCHLIST))
    parser.add_argument("--portfolio", default=str(DEFAULT_PORTFOLIO))
    args = parser.parse_args()
    result = generate_alerts(watchlist_path=args.watchlist, portfolio_path=args.portfolio)
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else format_alerts(result))


if __name__ == "__main__":
    main()
