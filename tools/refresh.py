"""Daily refresh: capture live snapshot and cache a backtest summary."""
from __future__ import annotations

import json
import os

import backtest
import snapshot
import store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(ROOT, "reports")


def main() -> None:
    captured = snapshot.capture()
    codes = store.codes_with_history(120)
    result = backtest.evaluate_many(codes, horizon=20)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, "backtest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"captured={captured} backtest_codes={len(codes)} cache={path}")


if __name__ == "__main__":
    main()
