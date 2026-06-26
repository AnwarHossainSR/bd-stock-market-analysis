"""DSE Scraper API — thin FastAPI layer over the tools/ scraper + report engines.

Run from project root:
    .venv/Scripts/uvicorn api.main:app --port 8000
    # docs at http://localhost:8000/docs

Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import analysis, market, portfolio, reports

app = FastAPI(
    title="DSE Scraper API",
    version="1.0",
    description="Read-only Dhaka Stock Exchange data (scraped from dsebd.org) + PDF report. "
                "Educational only, NOT financial advice.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["meta"])
def health():
    return {"ok": True}


app.include_router(analysis.router)
app.include_router(market.router)
app.include_router(portfolio.router)
app.include_router(reports.router)
