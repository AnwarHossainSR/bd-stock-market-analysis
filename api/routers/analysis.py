"""One-shot endpoint: everything the CLI chain does, in a single call.

GET /api/analysis  ==  index + screen + portfolio P&L + PDF report, bundled.
"""
from __future__ import annotations

import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.core import PORTFOLIO_CSV, analysis_runs, report, dse, session

router = APIRouter(prefix="/api", tags=["analysis"])


class CommentaryIn(BaseModel):
    commentary_md: str = ""


def _analysis_payload(
    buy: int = Query(6, ge=1, le=20),
    watch: int = Query(6, ge=0, le=20),
    cash: float = Query(0.0, ge=0),
    investor: str | None = Query(None),
    pdf: bool = Query(True, description="also build the PDF report"),
) -> dict:
    rows = dse.get_prices()
    slim = lambda r: {"code": r["code"], "ltp": r["ltp"],
                      "pct_change": dse._pct_change(r), "value_mn": r["value_mn"]}
    gainers = sorted(rows, key=dse._pct_change, reverse=True)[:10]
    losers = sorted(rows, key=dse._pct_change)[:10]
    actives = sorted(rows, key=lambda r: r.get("value_mn") or 0, reverse=True)[:10]

    data = report.select(buy, watch)  # regime, breadth, buy, watch, avoid
    port = report.load_portfolio(PORTFOLIO_CSV)

    out = {
        "fetched_at": dse._now(),
        "market": {
            "regime": data["regime"],
            "breadth": data["breadth"],
            "top_gainers": [slim(r) for r in gainers],
            "top_losers": [slim(r) for r in losers],
            "most_active_by_value": [slim(r) for r in actives],
        },
        "screen": {"buy": data["buy"], "watch": data["watch"], "avoid": data["avoid"]},
        "portfolio": port,
        "session": {"market_state": session.market_state()},
        "disclaimer": "Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice.",
    }
    if pdf:
        path = report.build_pdf(data, port, datetime.now(), investor=investor, cash=cash)
        name = os.path.basename(path)
        out["report"] = {"url": f"/reports/{name}", "file": name}
    return out


@router.get("/analysis")
def analysis(
    buy: int = Query(6, ge=1, le=20),
    watch: int = Query(6, ge=0, le=20),
    cash: float = Query(0.0, ge=0),
    investor: str | None = Query(None),
    pdf: bool = Query(True, description="also build the PDF report"),
):
    return _analysis_payload(buy=buy, watch=watch, cash=cash, investor=investor, pdf=pdf)


@router.post("/analysis/runs")
def create_analysis_run(
    buy: int = Query(6, ge=1, le=20),
    watch: int = Query(6, ge=0, le=20),
    cash: float = Query(0.0, ge=0),
    investor: str | None = Query(None),
    source: str = Query("ui", pattern="^(ui|slash|manual)$"),
):
    report_status = "ok"
    report_error = None
    try:
        payload = _analysis_payload(buy=buy, watch=watch, cash=cash, investor=investor, pdf=True)
    except Exception as exc:
        report_status = "failed"
        report_error = str(exc)
        payload = _analysis_payload(buy=buy, watch=watch, cash=cash, investor=investor, pdf=False)
    return analysis_runs.save_run(payload, source=source, report_status=report_status, report_error=report_error)


@router.get("/analysis/runs")
def list_analysis_runs(limit: int = Query(20, ge=1, le=100)):
    return {"runs": analysis_runs.list_runs(limit=limit)}


@router.get("/analysis/runs/latest")
def latest_analysis_run():
    record = analysis_runs.latest_run()
    if not record:
        raise HTTPException(404, "analysis run not found")
    return record


@router.get("/analysis/runs/{run_id}")
def get_analysis_run(run_id: str):
    record = analysis_runs.get_run(run_id)
    if not record:
        raise HTTPException(404, "analysis run not found")
    return record


@router.post("/analysis/runs/{run_id}/commentary")
def save_analysis_commentary(run_id: str, body: CommentaryIn):
    record = analysis_runs.save_commentary(run_id, body.commentary_md)
    if not record:
        raise HTTPException(404, "analysis run not found")
    return record
