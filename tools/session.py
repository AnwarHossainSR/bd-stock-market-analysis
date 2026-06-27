"""Live-session action sheet for Dhaka Stock Exchange market hours.

Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

import dse
import portfolio_actions
import store

try:
    BD_TZ = ZoneInfo("Asia/Dhaka")
except ZoneInfoNotFoundError:
    BD_TZ = timezone(timedelta(hours=6), name="Asia/Dhaka")
DISCLAIMER = "Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice."
DEFAULT_PORTFOLIO = Path(__file__).resolve().parents[1] / "data" / "portfolio.csv"


def _pct_change(row: dict) -> float:
    ltp, ycp = row.get("ltp"), row.get("ycp")
    if ltp is None or not ycp:
        return 0.0
    return round((ltp - ycp) / ycp * 100, 2)


def market_state(now: datetime | None = None, holidays: set[str] | None = None) -> str:
    local = now.astimezone(BD_TZ) if now else datetime.now(BD_TZ)
    if local.strftime("%Y-%m-%d") in (holidays or set()):
        return "CLOSED"
    # DSE is currently Sunday-Thursday. Python weekday: Monday=0, Friday=4, Saturday=5, Sunday=6.
    if local.weekday() in (4, 5):
        return "CLOSED"
    t = local.time()
    if t < time(10, 0):
        return "PRE_MARKET"
    if time(10, 0) <= t < time(14, 0):
        return "LIVE"
    if time(14, 0) <= t < time(14, 10):
        return "POST_CLOSE"
    return "EOD"


def data_health(rows: list[dict], fetched_at: datetime | None = None, error: str | None = None) -> dict:
    warnings = []
    zero_ltp = sum(1 for r in rows if not r.get("ltp"))
    if error:
        warnings.append(error)
    if not rows:
        warnings.append("no price rows parsed")
    if zero_ltp:
        warnings.append(f"{zero_ltp} zero-LTP names ignored")
    status = "ERROR" if error or not rows else "WARN" if warnings else "OK"
    return {
        "status": status,
        "latest_scrape": (fetched_at or datetime.now(BD_TZ)).isoformat(timespec="seconds"),
        "rows": len(rows),
        "zero_ltp": zero_ltp,
        "warnings": warnings,
    }


def market_breadth(rows: list[dict]) -> dict:
    adv = dec = unch = 0
    value = 0.0
    for row in rows:
        pct = _pct_change(row)
        if pct > 0:
            adv += 1
        elif pct < 0:
            dec += 1
        else:
            unch += 1
        value += row.get("value_mn") or 0

    if adv > dec * 1.5:
        regime = "BULLISH"
    elif dec > adv * 1.5:
        regime = "BEARISH"
    else:
        regime = "MIXED"
    return {
        "regime": regime,
        "advances": adv,
        "declines": dec,
        "unchanged": unch,
        "total": len(rows),
        "total_value_mn": round(value, 2),
    }


def _slim(row: dict) -> dict:
    return {
        "code": row.get("code"),
        "ltp": row.get("ltp"),
        "high": row.get("high"),
        "low": row.get("low"),
        "pct_change": _pct_change(row),
        "value_mn": row.get("value_mn"),
        "volume": row.get("volume"),
        "trades": row.get("trades"),
    }


def _avg(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None]
    return sum(clean) / len(clean) if clean else None


def _history_volume_ratio(code: str, today_volume: float | None, db_path=None) -> float | None:
    if today_volume is None:
        return None
    hist = store.history(code, days=25, db_path=db_path)
    avg_volume = _avg([r.get("volume") for r in hist[-20:]])
    if not avg_volume:
        return None
    return round(today_volume / avg_volume, 2)


def unusual_volume_candidates(rows: list[dict], limit: int = 10, db_path=None) -> list[dict]:
    candidates = []
    for row in rows:
        ratio = _history_volume_ratio(row.get("code", ""), row.get("volume"), db_path=db_path)
        if ratio is None:
            continue
        if ratio >= 1.8 and (row.get("value_mn") or 0) >= 1:
            item = _slim(row)
            item["volume_ratio"] = ratio
            candidates.append(item)
    candidates.sort(key=lambda x: (x.get("volume_ratio") or 0, x.get("value_mn") or 0), reverse=True)
    return candidates[:limit]


def buy_watch_candidates(rows: list[dict], limit: int = 10, db_path=None) -> list[dict]:
    candidates = []
    for row in rows:
        pct = _pct_change(row)
        value = row.get("value_mn") or 0
        high, low, ltp = row.get("high"), row.get("low"), row.get("ltp")
        day_position = (ltp - low) / (high - low) if None not in (ltp, high, low) and high > low else None
        volume_ratio = _history_volume_ratio(row.get("code", ""), row.get("volume"), db_path=db_path)
        has_participation = value >= 3 or (volume_ratio is not None and volume_ratio >= 1.5)
        if 1.0 <= pct < 7.0 and has_participation and (day_position is None or day_position >= 0.55):
            item = _slim(row)
            item["label"] = "BUY-WATCH"
            item["volume_ratio"] = volume_ratio
            item["reason"] = f"{pct:+.2f}% with {value:.2f}mn value"
            candidates.append(item)
    candidates.sort(key=lambda x: (x.get("value_mn") or 0, x.get("pct_change") or 0), reverse=True)
    return candidates[:limit]


def avoid_chase_warnings(rows: list[dict], limit: int = 10) -> list[dict]:
    warnings = []
    for row in rows:
        pct = _pct_change(row)
        value = row.get("value_mn") or 0
        if pct >= 7:
            item = _slim(row)
            item["label"] = "DO NOT CHASE"
            item["reason"] = f"spike {pct:+.2f}% near upper-circuit risk"
            warnings.append(item)
        elif pct <= -7:
            item = _slim(row)
            item["label"] = "AVOID"
            item["reason"] = f"crash {pct:+.2f}% - wait for stabilization"
            warnings.append(item)
        elif value < 0.5 and row.get("ltp"):
            item = _slim(row)
            item["label"] = "AVOID"
            item["reason"] = f"thin value traded {value:.2f}mn"
            warnings.append(item)
    warnings.sort(key=lambda x: abs(x.get("pct_change") or 0), reverse=True)
    return warnings[:limit]


def auto_watchlist_rows(rows: list[dict], limit: int = 10, db_path=None) -> list[dict]:
    """Generate watchlist CSV rows from today's BUY-WATCH candidates."""
    out = []
    for item in buy_watch_candidates(rows, limit=limit, db_path=db_path):
        ltp = item.get("ltp")
        low = item.get("low")
        high = item.get("high")
        if ltp is None:
            continue
        entry_below = low if low is not None else ltp * 0.98
        breakout_above = high if high is not None else ltp * 1.02
        stop = entry_below * 0.97
        note_bits = ["auto BUY-WATCH", item.get("reason")]
        if item.get("volume_ratio") is not None:
            note_bits.append(f"volume {item['volume_ratio']}x")
        out.append(
            {
                "code": item["code"],
                "entry_below": round(entry_below, 2),
                "breakout_above": round(breakout_above, 2),
                "stop": round(stop, 2),
                "notes": "; ".join(x for x in note_bits if x),
            }
        )
    return out


def build_action_sheet(
    prices: list[dict],
    portfolio_path: str | Path | None = DEFAULT_PORTFOLIO,
    now: datetime | None = None,
    limit: int = 10,
    db_path=None,
) -> dict:
    local_now = now.astimezone(BD_TZ) if now else datetime.now(BD_TZ)
    rows = [r for r in prices if r.get("code")]
    breadth = market_breadth(rows)
    holdings = portfolio_actions.load_portfolio(portfolio_path) if portfolio_path else []
    portfolio = portfolio_actions.analyze_portfolio(holdings, rows, db_path=db_path) if holdings else None

    sorted_by_change = sorted(rows, key=_pct_change, reverse=True)
    sorted_by_value = sorted(rows, key=lambda r: r.get("value_mn") or 0, reverse=True)

    return {
        "generated_at": local_now.isoformat(timespec="seconds"),
        "market_state": market_state(local_now),
        "data_health": data_health(rows, fetched_at=local_now),
        "market": breadth,
        "top_value_movers": [_slim(r) for r in sorted_by_value[:limit]],
        "top_gainers": [_slim(r) for r in sorted_by_change[:limit]],
        "top_losers": [_slim(r) for r in sorted_by_change[-limit:]][::-1],
        "unusual_volume": unusual_volume_candidates(rows, limit=limit, db_path=db_path),
        "buy_watch": buy_watch_candidates(rows, limit=limit, db_path=db_path),
        "auto_watchlist": auto_watchlist_rows(rows, limit=limit, db_path=db_path),
        "avoid_chase_warnings": avoid_chase_warnings(rows, limit=limit),
        "portfolio": portfolio,
        "portfolio_danger_names": portfolio.get("danger", []) if portfolio else [],
        "disclaimer": DISCLAIMER,
    }


def get_action_sheet(portfolio_path: str | Path | None = DEFAULT_PORTFOLIO, limit: int = 10, db_path=None) -> dict:
    try:
        prices = dse.get_prices()
    except requests.RequestException as exc:
        return {
            "generated_at": datetime.now(BD_TZ).isoformat(timespec="seconds"),
            "market_state": market_state(),
            "data_health": data_health([], error=f"DSE fetch failed: {exc}"),
            "market": market_breadth([]),
            "portfolio": None,
            "portfolio_danger_names": [],
            "top_value_movers": [],
            "top_gainers": [],
            "top_losers": [],
            "unusual_volume": [],
            "buy_watch": [],
            "auto_watchlist": [],
            "avoid_chase_warnings": [],
            "disclaimer": DISCLAIMER,
        }
    return build_action_sheet(prices, portfolio_path=portfolio_path, limit=limit, db_path=db_path)


def _fmt_item(item: dict) -> str:
    if item.get("entry_below") is not None:
        return (
            f"{item.get('code', 'N/A')} | entry <= {item['entry_below']} | "
            f"breakout > {item.get('breakout_above', 'n/a')} | stop {item.get('stop', 'n/a')} | "
            f"{item.get('notes', '')}"
        ).strip()
    pieces = [item.get("code", "N/A")]
    if item.get("ltp") is not None:
        pieces.append(f"LTP {item['ltp']}")
    pieces.append(f"{item.get('pct_change', 0):+.2f}%")
    if item.get("value_mn") is not None:
        pieces.append(f"value {item['value_mn']}mn")
    if item.get("volume_ratio") is not None:
        pieces.append(f"vol {item['volume_ratio']}x")
    if item.get("label"):
        pieces.append(item["label"])
    return " | ".join(pieces)


def format_action_sheet(sheet: dict) -> str:
    health = sheet["data_health"]
    market = sheet["market"]
    lines = [
        f"DSE SESSION ACTION SHEET | {sheet['generated_at']}",
        f"Market state: {sheet['market_state']}",
        f"Data health: {health['status']} | rows {health['rows']} | warnings: {', '.join(health['warnings']) or 'none'}",
        f"Market: {market['regime']} | adv {market['advances']} / dec {market['declines']} / unch {market['unchanged']} | value {market['total_value_mn']}mn",
        "",
        "Portfolio actions:",
    ]
    portfolio = sheet.get("portfolio")
    if portfolio:
        table = portfolio_actions.format_action_table(portfolio)
        lines.append(table or "No portfolio positions.")
    else:
        lines.append("No portfolio file loaded.")

    sections = [
        ("Top value movers", sheet.get("top_value_movers", [])[:5]),
        ("Top gainers", sheet.get("top_gainers", [])[:5]),
        ("Top losers", sheet.get("top_losers", [])[:5]),
        ("Unusual volume", sheet.get("unusual_volume", [])[:5]),
        ("Buy-watch candidates", sheet.get("buy_watch", [])[:5]),
        ("Auto watchlist rows", sheet.get("auto_watchlist", [])[:5]),
        ("Avoid/chase warnings", sheet.get("avoid_chase_warnings", [])[:5]),
    ]
    for title, items in sections:
        lines.extend(["", f"{title}:"])
        lines.extend([_fmt_item(x) for x in items] or ["None."])

    lines.extend(["", DISCLAIMER])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="DSE trading-session decision-support action sheet")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    parser.add_argument("--portfolio", default=str(DEFAULT_PORTFOLIO), help="portfolio CSV path")
    parser.add_argument("--limit", type=int, default=10, help="rows per section")
    parser.add_argument("--write-watchlist", help="write generated BUY-WATCH rows to this CSV path")
    args = parser.parse_args()

    sheet = get_action_sheet(portfolio_path=args.portfolio, limit=args.limit)
    if args.write_watchlist:
        import csv

        out = Path(args.write_watchlist)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["code", "entry_below", "breakout_above", "stop", "notes"])
            writer.writeheader()
            writer.writerows(sheet.get("auto_watchlist", []))
    if args.json:
        print(json.dumps(sheet, indent=2, ensure_ascii=False))
    else:
        print(format_action_sheet(sheet))


if __name__ == "__main__":
    main()
