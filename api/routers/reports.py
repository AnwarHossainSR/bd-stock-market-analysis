"""Report endpoints: build the dated PDF and serve it."""
from __future__ import annotations

import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from api.core import PORTFOLIO_CSV, REPORTS_DIR, report

router = APIRouter(tags=["reports"])


@router.get("/api/report")
def make_report(
    buy: int = Query(6, ge=1, le=20),
    watch: int = Query(6, ge=0, le=20),
    cash: float = Query(0.0, ge=0),
    investor: str | None = Query(None),
):
    data = report.select(buy, watch)
    port = report.load_portfolio(PORTFOLIO_CSV)
    path = report.build_pdf(data, port, datetime.now(), investor=investor, cash=cash)
    name = os.path.basename(path)
    return {"url": f"/reports/{name}", "file": name}


@router.get("/reports/{name}")
def get_report(name: str):
    path = os.path.join(REPORTS_DIR, os.path.basename(name))
    if not os.path.isfile(path) or not path.endswith(".pdf"):
        raise HTTPException(404, "report not found")
    return FileResponse(path, media_type="application/pdf", filename=name)
