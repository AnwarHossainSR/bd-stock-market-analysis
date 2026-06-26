"""EOD snapshot endpoints: capture today's market + per-ticker history."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import DailySnapshot
from app.services import dse

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])


@router.post("/capture")
async def capture(db: AsyncSession = Depends(get_db)):
    today = date.today()
    rows = dse.get_prices()
    existing = {
        s.code: s
        for s in (await db.execute(
            select(DailySnapshot).where(DailySnapshot.trade_date == today)
        )).scalars().all()
    }
    n = 0
    for r in rows:
        code = r["code"]
        fields = dict(
            ltp=r.get("ltp"), pct_change=dse._pct_change(r),
            value_mn=r.get("value_mn"), volume=r.get("volume"), tag=dse._rate(r)[0],
        )
        if code in existing:
            s = existing[code]
            for k, v in fields.items():
                setattr(s, k, v)
        else:
            db.add(DailySnapshot(trade_date=today, code=code, **fields))
        n += 1
    await db.commit()
    return {"captured": n, "trade_date": today.isoformat()}


@router.get("")
async def history(code: str = Query(...), days: int = Query(30, ge=1, le=365),
                  db: AsyncSession = Depends(get_db)):
    since = date.today() - timedelta(days=days)
    rows = (await db.execute(
        select(DailySnapshot)
        .where(DailySnapshot.code == code.upper(), DailySnapshot.trade_date >= since)
        .order_by(DailySnapshot.trade_date)
    )).scalars().all()
    return [
        {"trade_date": s.trade_date.isoformat(), "code": s.code, "ltp": s.ltp,
         "pct_change": s.pct_change, "value_mn": s.value_mn, "tag": s.tag}
        for s in rows
    ]
