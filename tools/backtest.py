"""Walk-forward validation: did past signals lead to positive forward returns?"""
from __future__ import annotations

import argparse
import json

import indicators as ind
import patterns
import score
import store


def evaluate(code, horizon=20, db_path=None):
    hist = store.history(code, days=2000, db_path=db_path)
    buckets = {}
    start = 20 if len(hist) < 80 else 60
    for i in range(start, len(hist) - horizon):
        window = hist[: i + 1]
        row = {
            "value_mn": window[-1].get("value_mn") or 0,
            "ltp": window[-1].get("close"),
            "ycp": window[-1].get("ycp") or (window[-2].get("close") if len(window) > 1 else None),
        }
        ic = ind.compute(window)
        pt = patterns.analyze(window, ic)
        sig = score.composite(row, ic, pt, None)["signal"]
        entry = window[-1].get("close")
        exit_ = hist[i + horizon].get("close")
        if not entry or not exit_:
            continue
        ret = (exit_ - entry) / entry * 100
        b = buckets.setdefault(sig, {"n": 0, "wins": 0, "sum": 0.0})
        b["n"] += 1
        b["sum"] += ret
        b["wins"] += 1 if ret > 0 else 0
    by = {
        s: {
            "n": b["n"],
            "win_rate": round(b["wins"] / b["n"] * 100, 1),
            "avg_ret": round(b["sum"] / b["n"], 2),
        }
        for s, b in buckets.items()
        if b["n"]
    }
    return {"code": code, "horizon": horizon, "by_signal": by}


def evaluate_many(codes, horizon=20, db_path=None):
    agg = {}
    for code in codes:
        for sig, val in evaluate(code, horizon, db_path).get("by_signal", {}).items():
            a = agg.setdefault(sig, {"n": 0, "wins": 0.0, "sum": 0.0})
            a["n"] += val["n"]
            a["wins"] += val["win_rate"] * val["n"] / 100
            a["sum"] += val["avg_ret"] * val["n"]
    return {
        "horizon": horizon,
        "by_signal": {
            sig: {
                "n": a["n"],
                "win_rate": round(a["wins"] / a["n"] * 100, 1) if a["n"] else 0,
                "avg_ret": round(a["sum"] / a["n"], 2) if a["n"] else 0,
            }
            for sig, a in agg.items()
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=20)
    ap.add_argument("--code")
    args = ap.parse_args()
    codes = [args.code] if args.code else store.codes_with_history(min_rows=120)
    print(json.dumps(evaluate_many(codes, args.horizon), indent=2))


if __name__ == "__main__":
    main()
