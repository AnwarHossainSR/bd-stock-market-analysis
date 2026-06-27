"""Auto-generate a watchlist CSV from the live DSE session scanner."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import session

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "watchlist.csv"


def write_watchlist(rows: list[dict], path: str | Path = DEFAULT_OUT) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["code", "entry_below", "breakout_above", "stop", "notes"])
        writer.writeheader()
        writer.writerows(rows)
    return out


def generate(limit: int = 10, portfolio_path=None, db_path=None) -> list[dict]:
    sheet = session.get_action_sheet(portfolio_path=portfolio_path or session.DEFAULT_PORTFOLIO, limit=limit, db_path=db_path)
    return sheet.get("auto_watchlist", [])


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate watchlist.csv from today's BUY-WATCH candidates")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--write", nargs="?", const=str(DEFAULT_OUT), help="write CSV, default data/watchlist.csv")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    rows = generate(limit=args.limit)
    if args.write:
        path = write_watchlist(rows, args.write)
        print(path)
    elif args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        for row in rows:
            print(f"{row['code']} | entry <= {row['entry_below']} | breakout > {row['breakout_above']} | stop {row['stop']} | {row['notes']}")


if __name__ == "__main__":
    main()
