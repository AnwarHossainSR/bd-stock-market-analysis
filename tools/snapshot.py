"""Capture today's EOD snapshot from the live price page into the store."""
from __future__ import annotations

from datetime import date

import dse
import store


def capture(db_path=None, today=None) -> int:
    d = today or date.today().isoformat()
    rows = []
    for row in dse.get_prices():
        rows.append(
            {
                "date": d,
                "code": row["code"],
                "open": None,
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("ltp"),
                "ycp": row.get("ycp"),
                "ltp": row.get("ltp"),
                "volume": row.get("volume"),
                "value_mn": row.get("value_mn"),
                "trades": row.get("trades"),
            }
        )
    return store.upsert_prices(rows, db_path)


if __name__ == "__main__":
    print(capture())
