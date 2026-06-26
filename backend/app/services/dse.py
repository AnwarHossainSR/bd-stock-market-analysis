"""DSE (Dhaka Stock Exchange) scraper core.

Scrapes the public dsebd.org website (no API key, delayed/EOD data) and exposes
parsing + screening primitives consumed by the API routers and the screen/pdf
services. This is the single source of truth — the `tools/dse.py` CLI shim and
all FastAPI routers import from here.

dsebd.org ships an incomplete TLS chain, so `_get` retries once without
verification (public data, no credentials sent). Set DSE_INSECURE=0 for strict TLS.
"""
from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://www.dsebd.org"
PRICES_URL = f"{BASE}/latest_share_price_scroll_l.php"
COMPANY_URL = f"{BASE}/displayCompany.php?name={{code}}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) market-analysis-agent/1.0"

CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache"
CACHE_TTL = 60  # seconds; DSE data is delayed anyway, avoid hammering the site


# --------------------------------------------------------------------------- #
# HTTP + cache
# --------------------------------------------------------------------------- #
def _cache_path(key: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", key)
    return CACHE_DIR / (safe + ".html")


def _get(url: str) -> requests.Response:
    headers = {"User-Agent": UA}
    try:
        return requests.get(url, headers=headers, timeout=30)
    except requests.exceptions.SSLError:
        if os.environ.get("DSE_INSECURE") == "0":
            raise
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        print(
            "warning: dsebd.org TLS chain incomplete - retrying without verification "
            "(public data, no credentials sent)",
            file=sys.stderr,
        )
        return requests.get(url, headers=headers, timeout=30, verify=False)


def fetch(url: str, key: str, ttl: int = CACHE_TTL) -> str:
    """GET url with a small on-disk TTL cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cp = _cache_path(key)
    if ttl and cp.exists() and (time.time() - cp.stat().st_mtime) < ttl:
        return cp.read_text(encoding="utf-8", errors="ignore")
    resp = _get(url)
    resp.raise_for_status()
    html = resp.text
    cp.write_text(html, encoding="utf-8", errors="ignore")
    return html


def _num(text: str | None):
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
        rows.append(
            {
                "code": a.get_text(strip=True),
                "ltp": _num(tds[2].get_text()),
                "high": _num(tds[3].get_text()),
                "low": _num(tds[4].get_text()),
                "close": _num(tds[5].get_text()),
                "ycp": _num(tds[6].get_text()),
                "change": _num(tds[7].get_text()),
                "trades": _num(tds[8].get_text()),
                "value_mn": _num(tds[9].get_text()),
                "volume": _num(tds[10].get_text()),
            }
        )
    return rows


def get_prices(ttl: int = CACHE_TTL) -> list[dict]:
    return parse_prices(fetch(PRICES_URL, "prices", ttl))


def _pct_change(r: dict) -> float:
    ltp, ycp = r.get("ltp"), r.get("ycp")
    if ltp is None or not ycp:
        return 0.0
    return round((ltp - ycp) / ycp * 100, 2)


# --------------------------------------------------------------------------- #
# Company fundamentals
# --------------------------------------------------------------------------- #
def parse_company(html: str, code: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    cells = [c.get_text(" ", strip=True) for c in soup.find_all(["td", "th"])]

    def after(label: str):
        for i, c in enumerate(cells):
            if c == label or c.startswith(label):
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
    text = soup.get_text(" ", strip=True)
    md = re.search(r"((?:\d+(?:\.\d+)?%\s*\d{4}\s*,?\s*){2,})", text)
    data["dividend_history"] = md.group(1).strip().rstrip(",") if md else None
    m = re.search(r"P/E\s*(?:at a glance)?[\s\S]{0,400}?(\d+\.\d+)", html)
    data["pe"] = float(m.group(1)) if m else None
    return data


# --------------------------------------------------------------------------- #
# Rule-based screen tag (price/volume only) — NOT advice
# --------------------------------------------------------------------------- #
def _rate(r: dict):
    ltp, ycp, high, low = r.get("ltp"), r.get("ycp"), r.get("high"), r.get("low")
    val = r.get("value_mn") or 0
    if ltp is None or not ycp:
        return "NO-DATA", "no price"
    pct = (ltp - ycp) / ycp * 100
    if val < 0.5:
        return "AVOID", f"illiquid ({val:.2f}mn traded) - hard exit"
    if pct <= -7:
        return "AVOID", f"crash {pct:.1f}% - falling knife / near lower circuit"
    if pct >= 7:
        return "WAIT", f"spike {pct:.1f}% - overbought / near upper circuit, don't chase"
    pos = (ltp - low) / (high - low) if (high and low and high > low) else None
    if 1.5 <= pct < 7 and val >= 3 and (pos is None or pos >= 0.6):
        return "BUY-WATCH", f"+{pct:.1f}% on {val:.1f}mn vol, closing strong"
    if -7 < pct <= -2 and val >= 3:
        return "WATCH-DIP", f"{pct:.1f}% dip on volume - watch for support"
    if -2 < pct < 1.5:
        return "HOLD", f"stable {pct:+.1f}%"
    return "NEUTRAL", f"{pct:+.1f}%"
