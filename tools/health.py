"""Data quality guard for DSE session tooling."""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests

import dse
import portfolio_actions
import store

DISCLAIMER = "Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice."
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORTFOLIO = ROOT / "data" / "portfolio.csv"


def _cache_age_seconds() -> float | None:
    path = Path(dse.CACHE_DIR) / "prices.html"
    if not path.exists():
        return None
    return round(time.time() - os.path.getmtime(path), 2)


def _intraday_latest_ts(db_path=None) -> str | None:
    store.init_db(db_path)
    with store.connect(db_path) as con:
        row = con.execute("SELECT MAX(ts) AS ts FROM intraday_prices").fetchone()
        return row["ts"] if row else None


def check_health(
    prices: list[dict] | None = None,
    portfolio_path: str | Path = DEFAULT_PORTFOLIO,
    db_path=None,
) -> dict:
    warnings = []
    error = None
    fetch_success = True
    rows = prices
    if rows is None:
        try:
            rows = dse.get_prices()
        except requests.RequestException as exc:
            rows = []
            fetch_success = False
            error = f"DSE fetch failed: {exc}"
            warnings.append(error)

    zero_ltp = sum(1 for r in rows if not r.get("ltp"))
    if not rows:
        warnings.append("no parsed price rows")
    if zero_ltp:
        warnings.append(f"{zero_ltp} zero-LTP names ignored")

    cache_age = _cache_age_seconds()
    if cache_age is not None and cache_age > 300:
        warnings.append(f"price cache age {round(cache_age / 60, 1)} minutes")

    holdings = portfolio_actions.load_portfolio(portfolio_path)
    by_code = {r.get("code", "").upper(): r for r in rows}
    missing_portfolio = [h["code"] for h in holdings if h["code"] not in by_code]
    if missing_portfolio:
        warnings.append("missing portfolio prices: " + ", ".join(missing_portfolio))

    db_latest_date = store.last_date(db_path)
    intraday_latest = _intraday_latest_ts(db_path)
    status = "ERROR" if error or not rows else "WARN" if warnings else "OK"
    return {
        "status": status,
        "fetch_success": fetch_success,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "rows": len(rows),
        "zero_ltp": zero_ltp,
        "cache_age_seconds": cache_age,
        "missing_portfolio_prices": missing_portfolio,
        "db_latest_date": db_latest_date,
        "intraday_latest_ts": intraday_latest,
        "warnings": warnings,
        "disclaimer": DISCLAIMER,
    }


def format_health(result: dict) -> str:
    return "\n".join(
        [
            f"DATA HEALTH: {result['status']}",
            f"rows: {result['rows']}",
            f"zero_ltp: {result['zero_ltp']}",
            f"db_latest_date: {result.get('db_latest_date') or 'n/a'}",
            f"intraday_latest_ts: {result.get('intraday_latest_ts') or 'n/a'}",
            f"warnings: {', '.join(result['warnings']) or 'none'}",
            DISCLAIMER,
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="DSE data quality guard")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--portfolio", default=str(DEFAULT_PORTFOLIO))
    args = parser.parse_args()
    result = check_health(portfolio_path=args.portfolio)
    print(json.dumps(result, indent=2, ensure_ascii=False) if args.json else format_health(result))


if __name__ == "__main__":
    main()
