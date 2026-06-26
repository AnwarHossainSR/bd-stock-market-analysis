#!/usr/bin/env python3
"""DSE (Dhaka Stock Exchange) data fetcher for the BD market-analysis agents.

Scrapes the public dsebd.org website. No API key required.
All output is JSON on stdout so the sub-agents can consume it directly.

Subcommands
-----------
  prices                  All latest share prices (whole market snapshot)
  quote CODE [CODE ...]   Latest price for one or more tickers
  company CODE            Company fundamentals (P/E, EPS, NAV, dividend, mkt cap...)
  index                   Market breadth summary (advances/declines, value traded)
  portfolio [CSV]         Read holdings CSV, fetch live prices, compute P&L

Examples
--------
  python tools/dse.py prices --limit 20
  python tools/dse.py quote GP BEXIMCO SQURPHARMA
  python tools/dse.py company GP
  python tools/dse.py index
  python tools/dse.py portfolio data/portfolio.csv

Data source: https://www.dsebd.org (delayed / end-of-day, unofficial scrape).
This is for personal research only. DSE provides no official API; HTML layout
may change and break the parser — adjust the selectors here if that happens.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

BASE = "https://www.dsebd.org"
PRICES_URL = f"{BASE}/latest_share_price_scroll_l.php"
COMPANY_URL = f"{BASE}/displayCompany.php?name={{code}}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) market-analysis-agent/1.0"

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache")
CACHE_TTL = 60  # seconds; DSE data is delayed anyway, avoid hammering the site


# --------------------------------------------------------------------------- #
# HTTP + cache
# --------------------------------------------------------------------------- #
def _cache_path(key: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", key)
    return os.path.join(CACHE_DIR, safe + ".html")


def _get(url: str) -> requests.Response:
    """GET that tolerates dsebd.org's incomplete TLS chain.

    The site is public and unauthenticated (no credentials/cookies are sent),
    so on a TLS verification failure we retry once without verification. Set
    DSE_INSECURE=0 to force strict verification and fail instead.
    """
    headers = {"User-Agent": UA}
    try:
        return requests.get(url, headers=headers, timeout=30)
    except requests.exceptions.SSLError:
        if os.environ.get("DSE_INSECURE") == "0":
            raise
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        print("warning: dsebd.org TLS chain incomplete — retrying without verification "
              "(public data, no credentials sent)", file=sys.stderr)
        return requests.get(url, headers=headers, timeout=30, verify=False)


def fetch(url: str, key: str, ttl: int = CACHE_TTL) -> str:
    """GET url with a small on-disk TTL cache."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cp = _cache_path(key)
    if ttl and os.path.exists(cp) and (time.time() - os.path.getmtime(cp)) < ttl:
        with open(cp, encoding="utf-8", errors="ignore") as f:
            return f.read()
    resp = _get(url)
    resp.raise_for_status()
    html = resp.text
    with open(cp, "w", encoding="utf-8", errors="ignore") as f:
        f.write(html)
    return html


def _num(text: str):
    """Parse a numeric cell ('1,234.5', '--', '') -> float or None."""
    if text is None:
        return None
    t = text.replace(",", "").replace("\xa0", " ").strip()
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    return float(m.group()) if m else None


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# Prices (whole market)
# --------------------------------------------------------------------------- #
def parse_prices(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.find_all("tr"):
        a = tr.find("a", href=re.compile(r"displayCompany\.php\?name="))
        if not a:
            continue
        tds = tr.find_all("td")
        if len(tds) < 11:
            continue
        code = a.get_text(strip=True)
        rows.append({
            "code": code,
            "ltp": _num(tds[2].get_text()),
            "high": _num(tds[3].get_text()),
            "low": _num(tds[4].get_text()),
            "close": _num(tds[5].get_text()),
            "ycp": _num(tds[6].get_text()),
            "change": _num(tds[7].get_text()),
            "trades": _num(tds[8].get_text()),
            "value_mn": _num(tds[9].get_text()),
            "volume": _num(tds[10].get_text()),
        })
    return rows


def get_prices(ttl: int = CACHE_TTL) -> list[dict]:
    return parse_prices(fetch(PRICES_URL, "prices", ttl))


def cmd_prices(args):
    rows = get_prices()
    if args.sort == "value":
        rows.sort(key=lambda r: r["value_mn"] or 0, reverse=True)
    elif args.sort == "change":
        rows.sort(key=lambda r: _pct_change(r), reverse=True)
    if args.limit:
        rows = rows[: args.limit]
    return {"source": "DSE", "fetched_at": _now(), "count": len(rows), "prices": rows}


def _pct_change(r: dict):
    ltp, ycp = r.get("ltp"), r.get("ycp")
    if ltp is None or not ycp:
        return 0.0
    return round((ltp - ycp) / ycp * 100, 2)


# --------------------------------------------------------------------------- #
# Quote (specific tickers)
# --------------------------------------------------------------------------- #
def cmd_quote(args):
    wanted = {c.upper() for c in args.codes}
    rows = get_prices()
    by_code = {r["code"].upper(): r for r in rows}
    out = []
    for c in wanted:
        r = by_code.get(c)
        if r:
            r = dict(r)
            r["pct_change"] = _pct_change(r)
            out.append(r)
        else:
            out.append({"code": c, "error": "not found in latest price list"})
    return {"source": "DSE", "fetched_at": _now(), "quotes": out}


# --------------------------------------------------------------------------- #
# Company fundamentals
# --------------------------------------------------------------------------- #
def parse_company(html: str, code: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    cells = [c.get_text(" ", strip=True) for c in soup.find_all(["td", "th"])]

    def after(label: str):
        """Value sits either after the label inside the same cell, or in the next cell."""
        for i, c in enumerate(cells):
            if c == label or c.startswith(label + " ") or c.startswith(label):
                tail = c[len(label):].strip(" :")
                if tail:
                    return tail
                if i + 1 < len(cells) and cells[i + 1]:
                    return cells[i + 1]
        return None

    data = {
        "code": code.upper(),
        "last_trading_price": _num(after("Last Trading Price")),
        "market_cap_mn": _num(after("Market Capitalization (mn)")),
        "paid_up_capital_mn": _num(after("Paid-up Capital (mn)")),
        "authorized_capital_mn": _num(after("Authorized Capital (mn)")),
        "face_value": _num(after("Face/par Value")),
        "eps_basic": _num(after("Basic")),
        "market_category": after("Market Category"),
        "listing_year": _num(after("Listing Year")),
        "moving_range_52w": after("52 Weeks' Moving Range"),
        "sector": after("Sector"),
    }
    # Dividend history is a comma-list of "NNN% YYYY" — pull it directly.
    text = soup.get_text(" ", strip=True)
    md = re.search(r"((?:\d+(?:\.\d+)?%\s*\d{4}\s*,?\s*){2,})", text)
    data["dividend_history"] = md.group(1).strip().rstrip(",") if md else None
    # P/E — grab the first numeric near the P/E table header
    m = re.search(r"P/E\s*(?:at a glance)?[\s\S]{0,400}?(\d+\.\d+)", html)
    data["pe"] = float(m.group(1)) if m else None
    return data


def cmd_company(args):
    code = args.code.upper()
    html = fetch(COMPANY_URL.format(code=code), f"company_{code}", ttl=args.ttl)
    return {"source": "DSE", "fetched_at": _now(), "company": parse_company(html, code)}


# --------------------------------------------------------------------------- #
# Market breadth / index summary
# --------------------------------------------------------------------------- #
def cmd_index(args):
    rows = get_prices()
    adv = dec = unch = 0
    total_value = 0.0
    for r in rows:
        pc = _pct_change(r)
        if pc > 0:
            adv += 1
        elif pc < 0:
            dec += 1
        else:
            unch += 1
        total_value += r.get("value_mn") or 0
    gainers = sorted(rows, key=_pct_change, reverse=True)[:10]
    losers = sorted(rows, key=_pct_change)[:10]
    actives = sorted(rows, key=lambda r: r.get("value_mn") or 0, reverse=True)[:10]
    slim = lambda r: {"code": r["code"], "ltp": r["ltp"], "pct_change": _pct_change(r), "value_mn": r["value_mn"]}
    return {
        "source": "DSE",
        "fetched_at": _now(),
        "breadth": {"total_traded": len(rows), "advances": adv, "declines": dec, "unchanged": unch},
        "total_value_mn": round(total_value, 2),
        "top_gainers": [slim(r) for r in gainers],
        "top_losers": [slim(r) for r in losers],
        "most_active_by_value": [slim(r) for r in actives],
    }


# --------------------------------------------------------------------------- #
# Portfolio P&L
# --------------------------------------------------------------------------- #
def cmd_portfolio(args):
    path = args.csv
    if not os.path.exists(path):
        return {"error": f"portfolio file not found: {path}"}
    holdings = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row.get("code"):
                continue
            holdings.append({
                "code": row["code"].strip().upper(),
                "quantity": float(row["quantity"]),
                "buy_price": float(row["buy_price"]),
            })
    rows = get_prices()
    by_code = {r["code"].upper(): r for r in rows}
    positions, invested, market = [], 0.0, 0.0
    for h in holdings:
        r = by_code.get(h["code"])
        ltp = r["ltp"] if r else None
        cost = h["quantity"] * h["buy_price"]
        mval = h["quantity"] * ltp if ltp is not None else None
        pnl = (mval - cost) if mval is not None else None
        invested += cost
        market += mval or 0
        positions.append({
            **h,
            "ltp": ltp,
            "cost_value": round(cost, 2),
            "market_value": round(mval, 2) if mval is not None else None,
            "unrealized_pnl": round(pnl, 2) if pnl is not None else None,
            "pnl_pct": round(pnl / cost * 100, 2) if pnl is not None and cost else None,
            "day_change_pct": _pct_change(r) if r else None,
        })
    return {
        "source": "DSE",
        "fetched_at": _now(),
        "summary": {
            "invested": round(invested, 2),
            "market_value": round(market, 2),
            "unrealized_pnl": round(market - invested, 2),
            "return_pct": round((market - invested) / invested * 100, 2) if invested else None,
        },
        "positions": positions,
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main():
    p = argparse.ArgumentParser(description="DSE (Dhaka Stock Exchange) data fetcher")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("prices", help="all latest share prices")
    sp.add_argument("--limit", type=int, default=0)
    sp.add_argument("--sort", choices=["none", "value", "change"], default="none")
    sp.set_defaults(func=cmd_prices)

    sq = sub.add_parser("quote", help="latest price for tickers")
    sq.add_argument("codes", nargs="+")
    sq.set_defaults(func=cmd_quote)

    sc = sub.add_parser("company", help="company fundamentals")
    sc.add_argument("code")
    sc.add_argument("--ttl", type=int, default=3600)
    sc.set_defaults(func=cmd_company)

    si = sub.add_parser("index", help="market breadth summary")
    si.set_defaults(func=cmd_index)

    spf = sub.add_parser("portfolio", help="portfolio P&L from CSV")
    spf.add_argument("csv", nargs="?", default="data/portfolio.csv")
    spf.set_defaults(func=cmd_portfolio)

    args = p.parse_args()
    try:
        result = args.func(args)
    except requests.RequestException as e:
        result = {"error": f"network error: {e}"}
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
