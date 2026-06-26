"""Market data endpoints (read-only scrape)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.core import dse, report

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/prices")
def prices():
    """Whole-market snapshot, every traded share tagged."""
    rows = dse.get_prices()
    out = []
    for r in rows:
        tag, reason = dse._rate(r)
        out.append({**r, "pct_change": dse._pct_change(r), "tag": tag, "reason": reason})
    return {"fetched_at": dse._now(), "count": len(out), "prices": out}


@router.get("/quote")
def quote(codes: str = Query(..., description="comma-separated trading codes, e.g. GP,BEXIMCO")):
    want = [c.strip().upper() for c in codes.split(",") if c.strip()]
    by = {r["code"].upper(): r for r in dse.get_prices()}
    out = []
    for c in want:
        r = by.get(c)
        if r:
            out.append({**r, "pct_change": dse._pct_change(r), "tag": dse._rate(r)[0]})
        else:
            out.append({"code": c, "error": "not found in latest price list"})
    return {"fetched_at": dse._now(), "quotes": out}


@router.get("/company")
def company(code: str = Query(..., description="trading code, e.g. GP")):
    code = code.upper()
    try:
        html = dse.fetch(dse.COMPANY_URL.format(code=code), f"company_{code}", ttl=3600)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"scrape failed: {e}")
    c = dse.parse_company(html, code)
    by = {r["code"].upper(): r for r in dse.get_prices()}
    r = by.get(code, {})
    return {
        "company": {
            **c,
            **{k: r.get(k) for k in ("ltp", "high", "low", "ycp", "volume", "value_mn")},
            "pct_change": dse._pct_change(r) if r else None,
            "div_yield": report._div_yield(c, r.get("ltp") if r else None),
            "levels": report._levels({**r, "range_52w": c.get("moving_range_52w")}),
        }
    }


@router.get("/index")
def index():
    """Market breadth + top gainers/losers/most-active."""
    rows = dse.get_prices()
    adv = sum(1 for r in rows if dse._pct_change(r) > 0)
    dec = sum(1 for r in rows if dse._pct_change(r) < 0)
    slim = lambda r: {"code": r["code"], "ltp": r["ltp"],
                      "pct_change": dse._pct_change(r), "value_mn": r["value_mn"]}
    g = sorted(rows, key=dse._pct_change, reverse=True)[:10]
    l = sorted(rows, key=dse._pct_change)[:10]
    a = sorted(rows, key=lambda r: r.get("value_mn") or 0, reverse=True)[:10]
    return {
        "fetched_at": dse._now(),
        "breadth": {"total": len(rows), "advances": adv, "declines": dec,
                    "unchanged": len(rows) - adv - dec},
        "total_value_mn": round(sum(r.get("value_mn") or 0 for r in rows), 2),
        "top_gainers": [slim(r) for r in g],
        "top_losers": [slim(r) for r in l],
        "most_active_by_value": [slim(r) for r in a],
    }


@router.get("/overview")
def overview(buy: int = Query(6, ge=1, le=20), watch: int = Query(6, ge=0, le=20)):
    """Screened BUY / WATCH / AVOID buckets with fundamentals + levels."""
    return report.select(buy, watch)
