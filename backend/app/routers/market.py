"""Market data endpoints: overview (screen), full price table, company detail."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.services import dse, screen

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/overview")
def overview(buy: int = Query(6, ge=1, le=20), watch: int = Query(6, ge=0, le=20)):
    return screen.select(buy, watch)


@router.get("/prices")
def prices():
    rows = dse.get_prices()
    out = []
    for r in rows:
        tag, reason = dse._rate(r)
        out.append({**r, "pct_change": dse._pct_change(r), "tag": tag, "reason": reason})
    return {"fetched_at": dse._now(), "count": len(out), "prices": out}


@router.get("/company")
def company(code: str):
    if not code:
        raise HTTPException(400, "code required")
    code = code.upper()
    html = dse.fetch(dse.COMPANY_URL.format(code=code), f"company_{code}", ttl=3600)
    c = dse.parse_company(html, code)
    by = {r["code"].upper(): r for r in dse.get_prices()}
    r = by.get(code, {})
    return {
        "company": {
            **c,
            **{k: r.get(k) for k in ("ltp", "high", "low", "ycp", "volume", "value_mn")},
            "pct_change": dse._pct_change(r) if r else None,
            "div_yield": screen._div_yield(c, r.get("ltp") if r else None),
            "levels": screen._levels({**r, "range_52w": c.get("moving_range_52w")}),
        }
    }
