"""Local SQLite OHLC store for DSE shares."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "dse.db"
COLS = [
    "date",
    "code",
    "open",
    "high",
    "low",
    "close",
    "ycp",
    "ltp",
    "volume",
    "value_mn",
    "trades",
]


def connect(db_path=None):
    p = Path(db_path or DB_PATH)
    os.makedirs(p.parent, exist_ok=True)
    con = sqlite3.connect(str(p))
    con.row_factory = sqlite3.Row
    return con


def init_db(db_path=None) -> None:
    with connect(db_path) as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS prices(
                date TEXT,
                code TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                ycp REAL,
                ltp REAL,
                volume REAL,
                value_mn REAL,
                trades REAL,
                PRIMARY KEY(date, code)
            )"""
        )
        con.execute("CREATE INDEX IF NOT EXISTS ix_code_date ON prices(code, date)")
        con.execute(
            """CREATE TABLE IF NOT EXISTS intraday_prices(
                ts TEXT,
                code TEXT,
                ltp REAL,
                high REAL,
                low REAL,
                ycp REAL,
                volume REAL,
                value_mn REAL,
                trades REAL,
                PRIMARY KEY(ts, code)
            )"""
        )
        con.execute("CREATE INDEX IF NOT EXISTS ix_intraday_code_ts ON intraday_prices(code, ts)")


def upsert_prices(rows: list[dict], db_path=None) -> int:
    init_db(db_path)
    cols = ",".join(COLS)
    ph = ",".join("?" for _ in COLS)
    upd = ",".join(f"{c}=excluded.{c}" for c in COLS if c not in ("date", "code"))
    sql = f"INSERT INTO prices({cols}) VALUES({ph}) ON CONFLICT(date,code) DO UPDATE SET {upd}"
    n = 0
    with connect(db_path) as con:
        for row in rows:
            con.execute(sql, [row.get(c) for c in COLS])
            n += 1
    return n


def history(code: str, days: int = 420, db_path=None) -> list[dict]:
    init_db(db_path)
    with connect(db_path) as con:
        cur = con.execute(
            "SELECT * FROM prices WHERE code=? ORDER BY date DESC LIMIT ?",
            (code.upper(), days),
        )
        return [dict(r) for r in cur.fetchall()][::-1]


def last_date(db_path=None) -> str | None:
    init_db(db_path)
    with connect(db_path) as con:
        row = con.execute("SELECT MAX(date) AS d FROM prices").fetchone()
        return row["d"] if row else None


def codes_with_history(min_rows: int = 60, db_path=None) -> list[str]:
    init_db(db_path)
    with connect(db_path) as con:
        cur = con.execute(
            "SELECT code FROM prices GROUP BY code HAVING COUNT(*)>=? ORDER BY code",
            (min_rows,),
        )
        return [r["code"] for r in cur.fetchall()]
