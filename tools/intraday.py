"""Intraday snapshot store for live-session DSE scans."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import timezone, timedelta

import dse
import store

try:
    BD_TZ = ZoneInfo("Asia/Dhaka")
except ZoneInfoNotFoundError:
    BD_TZ = timezone(timedelta(hours=6), name="Asia/Dhaka")

INTRADAY_COLS = ["ts", "code", "ltp", "high", "low", "ycp", "volume", "value_mn", "trades"]


def _now(now: datetime | None = None) -> datetime:
    return now.astimezone(BD_TZ) if now else datetime.now(BD_TZ)


def _ts(now: datetime | None = None) -> str:
    return _now(now).isoformat(timespec="seconds")


def capture_intraday(db_path=None, now: datetime | None = None) -> int:
    """Fetch current DSE prices and persist one timestamped snapshot."""
    rows = dse.get_prices()
    store.init_db(db_path)
    ts = _ts(now)
    sql = (
        "INSERT INTO intraday_prices(ts,code,ltp,high,low,ycp,volume,value_mn,trades) "
        "VALUES(?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(ts,code) DO UPDATE SET "
        "ltp=excluded.ltp,high=excluded.high,low=excluded.low,ycp=excluded.ycp,"
        "volume=excluded.volume,value_mn=excluded.value_mn,trades=excluded.trades"
    )
    with store.connect(db_path) as con:
        for row in rows:
            con.execute(sql, [ts, row.get("code"), row.get("ltp"), row.get("high"), row.get("low"), row.get("ycp"), row.get("volume"), row.get("value_mn"), row.get("trades")])
    return len(rows)


def latest_intraday(code: str, db_path=None) -> dict | None:
    store.init_db(db_path)
    with store.connect(db_path) as con:
        row = con.execute(
            "SELECT * FROM intraday_prices WHERE code=? ORDER BY ts DESC LIMIT 1",
            (code.upper(),),
        ).fetchone()
        return dict(row) if row else None


def session_history(code: str, today=None, db_path=None) -> list[dict]:
    store.init_db(db_path)
    day = today
    if day is None:
        with store.connect(db_path) as con:
            row = con.execute(
                "SELECT MAX(substr(ts,1,10)) AS d FROM intraday_prices WHERE code=?",
                (code.upper(),),
            ).fetchone()
            day = row["d"] if row and row["d"] else _now().date().isoformat()
    with store.connect(db_path) as con:
        cur = con.execute(
            "SELECT * FROM intraday_prices WHERE code=? AND substr(ts,1,10)=? ORDER BY ts",
            (code.upper(), str(day)),
        )
        return [dict(r) for r in cur.fetchall()]


def price_velocity(code: str, window_minutes: int = 30, db_path=None) -> dict:
    rows = session_history(code, db_path=db_path)
    if len(rows) < 2:
        return {"code": code.upper(), "window_minutes": window_minutes, "pct_change": None, "points": len(rows)}
    latest = rows[-1]
    latest_ts = datetime.fromisoformat(latest["ts"])
    window_rows = [
        r for r in rows
        if (latest_ts - datetime.fromisoformat(r["ts"])).total_seconds() <= window_minutes * 60
    ]
    first = window_rows[0] if window_rows else rows[0]
    if not first.get("ltp") or latest.get("ltp") is None:
        pct = None
    else:
        pct = round((latest["ltp"] - first["ltp"]) / first["ltp"] * 100, 2)
    return {
        "code": code.upper(),
        "window_minutes": window_minutes,
        "from_ts": first["ts"],
        "to_ts": latest["ts"],
        "from_ltp": first.get("ltp"),
        "to_ltp": latest.get("ltp"),
        "pct_change": pct,
        "points": len(window_rows),
    }


def unusual_volume(code: str, db_path=None) -> dict:
    latest = latest_intraday(code, db_path=db_path)
    if not latest:
        return {"code": code.upper(), "volume_ratio": None, "status": "NO_INTRADAY"}
    hist = store.history(code, days=25, db_path=db_path)
    avg_volume = [r.get("volume") for r in hist[-20:] if r.get("volume") is not None]
    avg = sum(avg_volume) / len(avg_volume) if avg_volume else None
    ratio = round(latest["volume"] / avg, 2) if avg and latest.get("volume") is not None else None
    status = "SPIKE" if ratio is not None and ratio >= 1.8 else "NORMAL" if ratio is not None else "NO_BASELINE"
    return {
        "code": code.upper(),
        "latest_ts": latest.get("ts"),
        "volume": latest.get("volume"),
        "avg_daily_volume": round(avg, 2) if avg else None,
        "volume_ratio": ratio,
        "status": status,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture/read DSE intraday snapshots")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("capture")
    latest = sub.add_parser("latest")
    latest.add_argument("code")
    hist = sub.add_parser("history")
    hist.add_argument("code")
    vel = sub.add_parser("velocity")
    vel.add_argument("code")
    vel.add_argument("--window-minutes", type=int, default=30)
    uv = sub.add_parser("unusual-volume")
    uv.add_argument("code")
    args = parser.parse_args()

    if args.cmd == "capture":
        out = {"captured": capture_intraday()}
    elif args.cmd == "latest":
        out = latest_intraday(args.code)
    elif args.cmd == "history":
        out = session_history(args.code)
    elif args.cmd == "velocity":
        out = price_velocity(args.code, args.window_minutes)
    else:
        out = unusual_volume(args.code)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
