"""Report endpoints: build the dated PDF and serve it."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from api.core import PORTFOLIO_CSV, REPORTS_DIR, report

router = APIRouter(tags=["reports"])


@router.get("/api/reports")
def list_reports():
    root = Path(REPORTS_DIR)
    root.mkdir(parents=True, exist_ok=True)
    allowed = {".pdf", ".md"}
    files = []
    for path in root.iterdir():
        if not path.is_file() or path.suffix.lower() not in allowed:
            continue
        stat = path.stat()
        files.append(
            {
                "file": path.name,
                "url": f"/reports/{path.name}",
                "kind": path.suffix.lower().lstrip("."),
                "size": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            }
        )
    files.sort(key=lambda x: x["modified_at"], reverse=True)
    return {"reports": files}


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
    ext = os.path.splitext(path)[1].lower()
    if not os.path.isfile(path) or ext not in (".pdf", ".md"):
        raise HTTPException(404, "report not found")
    media_type = "application/pdf" if ext == ".pdf" else "text/markdown"
    return FileResponse(path, media_type=media_type, filename=name)
