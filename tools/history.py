"""Backfill historical OHLC from dsebd.org/day_end_archive.php into SQLite."""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime

from bs4 import BeautifulSoup

import dse
import store

ARCHIVE = "https://www.dsebd.org/day_end_archive.php"
_MAP = {
    "date": "date",
    "trading code": "code",
    "ltp": "ltp",
    "ltp*": "ltp",
    "high": "high",
    "low": "low",
    "openp": "open",
    "openp*": "open",
    "open": "open",
    "closep": "close",
    "closep*": "close",
    "close": "close",
    "ycp": "ycp",
    "ycp*": "ycp",
    "trade": "trades",
    "trades": "trades",
    "value (mn)": "value_mn",
    "value": "value_mn",
    "volume": "volume",
    "%change": "pct_change",
    "% change": "pct_change",
}


def _norm_header(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").strip().lower().split())


def _norm_date(text: str) -> str:
    t = text.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%b %d, %Y", "%d %b %Y"):
        try:
            return datetime.strptime(t, fmt).date().isoformat()
        except ValueError:
            pass
    return t


def parse_archive(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for tbl in soup.find_all("table"):
        head = tbl.find("tr")
        if not head:
            continue
        cols = [_norm_header(c.get_text(" ", strip=True)) for c in head.find_all(["th", "td"])]
        if "date" not in cols or not any("code" in c for c in cols):
            continue
        idx = {i: _MAP[c] for i, c in enumerate(cols) if c in _MAP}
        rows = []
        all_rows = tbl.find_all("tr")
        for tr in all_rows[all_rows.index(head) + 1:]:
            cells = tr.find_all("td")
            if len(cells) < len(cols):
                continue
            rec = {
                "open": None,
                "high": None,
                "low": None,
                "close": None,
                "ycp": None,
                "ltp": None,
                "volume": None,
                "value_mn": None,
                "trades": None,
            }
            for i, cell in enumerate(cells):
                key = idx.get(i)
                if not key or key == "pct_change":
                    continue
                txt = cell.get_text(" ", strip=True)
                rec[key] = txt if key in ("date", "code") else dse._num(txt)
            if rec.get("date") and rec.get("code"):
                rec["date"] = _norm_date(rec["date"])
                rec["code"] = rec["code"].upper()
                rows.append(rec)
        if rows:
            return rows
    return []


def fetch_archive(code, start, end) -> list[dict]:
    url = f"{ARCHIVE}?startDate={start}&endDate={end}&inst={code.upper()}&archive=data"
    return parse_archive(dse.fetch(url, f"archive_{code}_{start}_{end}", ttl=0))


def backfill(code, start, end, db_path=None) -> int:
    return store.upsert_prices(fetch_archive(code, start, end), db_path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--code")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--end", default=date.today().isoformat())
    args = ap.parse_args()
    if not args.all and not args.code:
        ap.error("--code or --all is required")
    codes = [r["code"] for r in dse.get_prices()] if args.all else [args.code]
    total = 0
    for code in codes:
        try:
            n = backfill(code, args.start, args.end)
            total += n
            print(f"{code}: {n}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"{code}: ERROR {exc}", file=sys.stderr)
    print(total)


if __name__ == "__main__":
    main()
