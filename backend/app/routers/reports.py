"""Report endpoints: build a dated PDF and serve it."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.config import settings
from app.services import pdf, screen

router = APIRouter(tags=["reports"])


@router.get("/api/report")
def make_report(buy: int = Query(6, ge=1, le=20), watch: int = Query(6, ge=0, le=20)):
    data = screen.select(buy, watch)
    path = pdf.build_pdf(data, datetime.now())
    return {"url": f"/reports/{path.name}", "file": path.name}


@router.get("/reports/{name}")
def get_report(name: str):
    path = settings.reports_dir / name
    if not path.is_file() or path.suffix != ".pdf":
        raise HTTPException(404, "report not found")
    return FileResponse(path, media_type="application/pdf", filename=name)
