"""Watchlist endpoints: CRUD with live price/tag enrichment."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import WatchlistItem
from app.schemas import WatchIn
from app.services import dse

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("")
async def list_watchlist(db: AsyncSession = Depends(get_db)):
    items = (await db.execute(select(WatchlistItem).order_by(WatchlistItem.created_at))).scalars().all()
    by = {r["code"].upper(): r for r in dse.get_prices()}
    out = []
    for it in items:
        r = by.get(it.code.upper())
        out.append({
            "id": it.id, "code": it.code, "note": it.note,
            "ltp": r["ltp"] if r else None,
            "pct_change": dse._pct_change(r) if r else None,
            "value_mn": r.get("value_mn") if r else None,
            "tag": dse._rate(r)[0] if r else "NO-DATA",
        })
    return out


@router.post("")
async def add_watch(body: WatchIn, db: AsyncSession = Depends(get_db)):
    code = body.code.strip().upper()
    existing = (await db.execute(select(WatchlistItem).where(WatchlistItem.code == code))).scalar_one_or_none()
    if existing:
        existing.note = body.note
    else:
        db.add(WatchlistItem(code=code, note=body.note))
    await db.commit()
    return {"ok": True, "code": code}


@router.delete("/{code}")
async def remove_watch(code: str, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(WatchlistItem).where(WatchlistItem.code == code.upper()))
    await db.commit()
    return {"ok": True}
