"""One-shot endpoint: everything the CLI chain does, in a single call.

GET /api/analysis  ==  index + screen + portfolio P&L + PDF report, bundled.
"""
from __future__ import annotations

import os
from datetime import datetime

from fastapi import APIRouter, Query

from api.core import PORTFOLIO_CSV, report, dse

router = APIRouter(prefix="/api", tags=["analysis"])


@router.get("/analysis")
def analysis(
    buy: int = Query(6, ge=1, le=20),
    watch: int = Query(6, ge=0, le=20),
    cash: float = Query(0.0, ge=0),
    investor: str | None = Query(None),
    pdf: bool = Query(True, description="also build the PDF report"),
):
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
        "disclaimer": "Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice.",
    }
    if pdf:
        path = report.build_pdf(data, port, datetime.now(), investor=investor, cash=cash)
        name = os.path.basename(path)
        out["report"] = {"url": f"/reports/{name}", "file": name}
    return out
