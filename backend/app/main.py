"""FastAPI application entrypoint for the DSE Terminal."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import market, portfolio, reports, snapshots, watchlist


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Best-effort DB bootstrap; market (scraper) features work even if DB is down.
    # Tests set DSE_SKIP_INIT=1 to stay hermetic (they use an aiosqlite override).
    if os.environ.get("DSE_SKIP_INIT") != "1":
        try:
            from app.init_db import init
            await init()
        except Exception as e:  # noqa: BLE001
            print(f"[startup] DB bootstrap skipped: {e}")
    yield


app = FastAPI(title="DSE Terminal API", version="1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True}


app.include_router(market.router)
app.include_router(portfolio.router)
app.include_router(watchlist.router)
app.include_router(snapshots.router)
app.include_router(reports.router)

# Serve the built React SPA at / when it exists (production).
if settings.frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(settings.frontend_dist), html=True), name="spa")
