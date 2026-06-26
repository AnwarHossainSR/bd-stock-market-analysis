"""Portfolio P&L: combine DB holdings with live prices."""
from __future__ import annotations

from app.services import dse


def compute_pnl(holdings, rows) -> dict:
    by = {r["code"].upper(): r for r in rows}
    positions, invested, market = [], 0.0, 0.0
    for h in holdings:
        r = by.get(h.code.upper())
        ltp = r["ltp"] if r else None
        cost = h.quantity * h.buy_price
        mval = h.quantity * ltp if ltp is not None else None
        pnl = (mval - cost) if mval is not None else None
        invested += cost
        market += mval or 0
        positions.append({
            "id": h.id, "code": h.code, "quantity": h.quantity, "buy_price": h.buy_price,
            "ltp": ltp,
            "market_value": round(mval, 2) if mval is not None else None,
            "unrealized_pnl": round(pnl, 2) if pnl is not None else None,
            "pnl_pct": round(pnl / cost * 100, 2) if pnl is not None and cost else None,
            "day_change_pct": dse._pct_change(r) if r else None,
            "tag": dse._rate(r)[0] if r else "NO-DATA",
        })
    return {
        "summary": {
            "invested": round(invested, 2),
            "market_value": round(market, 2),
            "unrealized_pnl": round(market - invested, 2),
            "return_pct": round((market - invested) / invested * 100, 2) if invested else None,
        },
        "positions": positions,
    }
