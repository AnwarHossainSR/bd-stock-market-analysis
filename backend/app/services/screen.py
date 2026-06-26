"""Screening service: turns the live market into BUY / WATCH / AVOID buckets
with fundamentals + trade levels. Reused by the API and the PDF report."""
from __future__ import annotations

import re

from app.services import dse


def _div_yield(company: dict, ltp):
    """Approx cash dividend yield % from latest dividend (% of face value)."""
    hist = company.get("dividend_history")
    fv = company.get("face_value")
    if not hist or not fv or not ltp:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", hist)
    if not m:
        return None
    cash_per_share = float(m.group(1)) / 100.0 * fv
    return round(cash_per_share / ltp * 100, 2)


def enrich(row: dict) -> dict:
    """Add fundamentals + 52w range to a screened row (company page, cached)."""
    code = row["code"]
    out = dict(row)
    try:
        html = dse.fetch(dse.COMPANY_URL.format(code=code), f"company_{code}", ttl=3600)
        c = dse.parse_company(html, code)
    except Exception:
        c = {}
    out["pe"] = c.get("pe")
    out["eps"] = c.get("eps_basic")
    out["category"] = c.get("market_category")
    out["sector"] = c.get("sector")
    out["range_52w"] = c.get("moving_range_52w")
    out["div_yield"] = _div_yield(c, row.get("ltp"))
    return out


def _levels(row: dict) -> dict:
    """Entry/stop/target from today's high/low + 52-week high."""
    high, low = row.get("high"), row.get("low")
    hi52 = None
    rng = row.get("range_52w")
    if rng:
        nums = re.findall(r"\d+(?:\.\d+)?", rng.replace(",", ""))
        if len(nums) >= 2:
            hi52 = float(nums[-1])
    return {
        "support": low,
        "resistance": high,
        "stop": round(low * 0.95, 1) if low else None,
        "target": hi52 or (round(high * 1.08, 1) if high else None),
    }


def select(buy_n: int, watch_n: int) -> dict:
    rows = dse.get_prices()
    rated = []
    for r in rows:
        tag, reason = dse._rate(r)
        r = dict(r)
        r["tag"], r["reason"], r["pct"] = tag, reason, dse._pct_change(r)
        rated.append(r)

    adv = sum(1 for x in rated if (x["pct"] or 0) > 0)
    dec = sum(1 for x in rated if (x["pct"] or 0) < 0)
    regime = "BULLISH" if adv > dec * 1.5 else "BEARISH" if dec > adv * 1.5 else "MIXED"

    buy = [r for r in rated if r["tag"] == "BUY-WATCH" and (r.get("value_mn") or 0) >= 5]
    buy.sort(key=lambda r: r.get("value_mn") or 0, reverse=True)
    buy = [enrich(r) for r in buy[:buy_n]]

    watch = [r for r in rated if r["tag"] in ("WATCH-DIP", "WAIT") and (r.get("value_mn") or 0) >= 3]
    watch.sort(key=lambda r: r.get("value_mn") or 0, reverse=True)
    watch = [enrich(r) for r in watch[:watch_n]]

    avoid_all = [r for r in rated if r["tag"] == "AVOID"]
    crash = sorted([r for r in avoid_all if (r.get("value_mn") or 0) >= 0.5],
                   key=lambda r: r.get("pct") or 0)
    notrade = [r for r in avoid_all if (r.get("value_mn") or 0) < 0.5]
    avoid = crash[:6] + notrade[:2]

    # attach levels for candidate cards
    for r in buy + watch:
        r["levels"] = _levels(r)

    return {
        "regime": regime,
        "breadth": {"adv": adv, "dec": dec, "total": len(rated),
                    "value_mn": round(sum(r.get("value_mn") or 0 for r in rated), 1)},
        "buy": buy, "watch": watch, "avoid": avoid,
        "note": "Rule-based price/volume screen - confirm with fundamentals + news. NOT financial advice.",
    }
