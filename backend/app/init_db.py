"""Database bootstrap: create the database if missing, create tables, seed holdings.

Runs on app startup (lifespan) and is safe to run standalone:
    .venv/Scripts/python -m app.init_db   (from backend/, PYTHONPATH=.)

Failures are non-fatal at startup so market features (scraper) keep working even
if PostgreSQL is down — only DB-backed endpoints will error in that case.
"""
from __future__ import annotations

import asyncio
import csv

from sqlalchemy import select
from sqlalchemy.engine import make_url

from app.config import settings
from app.db import Base, async_session, engine
from app import models  # noqa: F401  (register models on Base.metadata)


async def ensure_database() -> None:
    """CREATE DATABASE <name> if it does not exist (connects to 'postgres' db)."""
    url = make_url(settings.database_url)
    if not url.drivername.startswith("postgresql"):
        return  # sqlite/etc: nothing to create
    import asyncpg

    target = url.database
    conn = await asyncpg.connect(
        host=url.host or "localhost", port=url.port or 5432,
        user=url.username, password=url.password, database="postgres",
    )
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", target)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{target}"')
            print(f"[init_db] created database {target}")
    finally:
        await conn.close()


async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_holdings() -> None:
    """One-time seed from data/portfolio.csv if the holdings table is empty."""
    if not settings.seed_csv.exists():
        return
    async with async_session() as s:
        existing = (await s.execute(select(models.Holding))).first()
        if existing:
            return
        with open(settings.seed_csv, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if not row.get("code"):
                    continue
                s.add(models.Holding(
                    code=row["code"].strip().upper(),
                    quantity=float(row["quantity"]),
                    buy_price=float(row["buy_price"]),
                ))
        await s.commit()
        print("[init_db] seeded holdings from portfolio.csv")


async def init() -> None:
    await ensure_database()
    await create_tables()
    await seed_holdings()


if __name__ == "__main__":
    asyncio.run(init())
