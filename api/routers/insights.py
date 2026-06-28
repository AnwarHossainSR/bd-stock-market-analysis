"""History-backed insight endpoints."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from api.core import backtest, dse, fundamentals, history, indicators, patterns, score, snapshot, store

router = APIRouter(prefix="/api", tags=["insights"])


@router.get("/history")
def get_history(code: str, days: int = 420):
    return store.history(code, days)


@router.get("/indicators")
def get_indicators(code: str):
    h = store.history(code)
    if len(h) < 30:
        raise HTTPException(404, "not enough history - backfill first")
    return indicators.compute(h)


@router.get("/patterns")
def get_patterns(code: str):
    h = store.history(code)
    if len(h) < 30:
        raise HTTPException(404, "not enough history")
    return patterns.analyze(h, indicators.compute(h))


@router.get("/score")
def get_score(code: str | None = None, limit: int = Query(20, ge=1, le=100)):
    prices = {r["code"].upper(): r for r in dse.get_prices()}

    def one(c):
        h = store.history(c)
        if len(h) < 30:
            return None
        ic = indicators.compute(h)
        pt = patterns.analyze(h, ic)
        row = prices.get(c, {"code": c, "ltp": h[-1].get("close"), "ycp": h[-1].get("ycp"), "value_mn": h[-1].get("value_mn")})
        try:
            f = fundamentals.enrich_fundamentals(c, row.get("ltp"))
            fs, _ = fundamentals.fundamental_score(f)
        except Exception:
            fs = None
        return {"code": c, **score.composite(row, ic, pt, fs), "pattern": pt["summary"]}

    if code:
        result = one(code.upper())
        if not result:
            raise HTTPException(404, "not enough history")
        return result
    out = [one(c) for c in store.codes_with_history(60)]
    out = [x for x in out if x]
    return sorted(out, key=lambda x: x["score"], reverse=True)[:limit]


@router.get("/backtest")
def get_backtest(horizon: int = 20, code: str | None = None):
    codes = [code.upper()] if code else store.codes_with_history(120)
    return backtest.evaluate_many(codes, horizon)


@router.post("/snapshot/capture")
def post_capture():
    return {"captured": snapshot.capture()}


@router.post("/history/backfill")
def post_backfill(code: str, start: str = "2023-01-01", end: str | None = None):
    return {"stored": history.backfill(code, start, end or date.today().isoformat())}
