"""Portfolio endpoints: live P&L + replace/delete holdings (PostgreSQL-backed)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Holding
from app.schemas import PortfolioReplaceIn
from app.services import dse, pnl

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("")
async def get_portfolio(db: AsyncSession = Depends(get_db)):
    holdings = (await db.execute(select(Holding))).scalars().all()
    return pnl.compute_pnl(holdings, dse.get_prices())


@router.post("")
async def replace_portfolio(body: PortfolioReplaceIn, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(Holding))
    for h in body.holdings:
        db.add(Holding(code=h.code.upper(), quantity=h.quantity, buy_price=h.buy_price))
    await db.commit()
    holdings = (await db.execute(select(Holding))).scalars().all()
    return pnl.compute_pnl(holdings, dse.get_prices())


@router.delete("/{hid}")
async def delete_holding(hid: int, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(Holding).where(Holding.id == hid))
    await db.commit()
    return {"ok": True}
