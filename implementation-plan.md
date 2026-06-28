# DSE Analysis — Pro Accuracy Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the single-day price/volume screen into a defensible, multi-factor analysis engine — backed by real historical OHLC (SQLite), genuine technical indicators + chart-pattern reads, deeper fundamentals, a composite conviction score, a backtest that *measures* signal accuracy, and a professional PDF with embedded charts and portfolio analytics.

**Architecture:** Keep the existing lean layout (`tools/` = logic, `api/` = thin FastAPI over it). Add a local **SQLite** price store (`data/dse.db`) filled by (a) a one-time **historical backfill** scraping `dsebd.org/day_end_archive.php` and (b) a daily **EOD snapshot** from the live price page. New pure-Python modules compute indicators, patterns, fundamentals and a composite score from that history; a backtest module validates the signals on past data; matplotlib renders charts embedded into the upgraded PDF. Everything reuses the existing `tools/dse.py` scraper and `tools/report.py` engine — no duplication, no web server dependency for the core.

**Tech Stack:** Python 3.14 (existing `.venv`), `requests` + `beautifulsoup4` (scrape), `sqlite3` (stdlib, store), `numpy` (indicators), `matplotlib` (charts), `fpdf2` (PDF), `fastapi`/`uvicorn` (API), `pytest` (tests).

## Global Constraints

- **Python env:** always call `.venv/Scripts/python` and `.venv/Scripts/uvicorn` (Windows; sub-agents run non-interactive, no activation). Never bare `python`.
- **Run everything from the repo root** `d:\Workspace\own\Agentic-AI\market-analysis`.
- **Reuse, don't duplicate.** Scraper primitives live in `tools/dse.py` (`get_prices`, `fetch`, `COMPANY_URL`, `parse_company`, `_pct_change`, `_now`, `_num`, `_rate`). Report engine in `tools/report.py` (`select`, `enrich`, `_levels`, `_div_yield`, `load_portfolio`, `build_pdf`). API re-exports them via `api/core.py`. New modules import these; they do not re-implement scraping.
- **No new server / no Postgres / no React.** SQLite file only. The app stays CLI + FastAPI.
- **Accuracy honesty:** indicators/patterns/scores are quantitative aids, not predictions. Every output keeps the disclaimer: "Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice."
- **matplotlib must use the non-interactive Agg backend** (`matplotlib.use("Agg")` before pyplot) so it renders headless.
- **Tests must not hit the network:** parse from saved HTML fixtures; indicators/patterns/score/backtest run on synthetic or fixture-derived series; store tests use a temp DB file.
- **Caveman mode** applies to chat replies only — never to code, plan, README, or commits.
- **Commit footer** on every commit: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## Context

Today's screen (`tools/dse.py::_rate`) tags a share from **one day** of price + volume only. It cannot see trend, momentum, volatility, or whether a "pick" has historically worked — so accuracy is capped and unmeasurable. This plan adds a price **history store**, real **indicators** + **chart-pattern analysis**, **deeper fundamentals**, a transparent **composite score**, and a **backtest** to prove (and tune) accuracy — then surfaces all of it in a chart-rich PDF and the API. DSE exposes real historical OHLC at `day_end_archive.php` (columns: Date, Trading Code, LTP, High, Low, Open, Close, YCP, Trade, Value, Volume, %Change), so the engine is accurate from day one rather than after weeks of snapshots.

## Target file structure

```
tools/
  dse.py            # (existing) scraper primitives — unchanged except a tiny snapshot helper
  report.py         # (existing) upgraded: scores, patterns, charts, portfolio analytics
  store.py          # NEW  SQLite price store (schema, upsert, history queries)
  history.py        # NEW  backfill OHLC from day_end_archive.php  -> store
  snapshot.py       # NEW  capture today's EOD from live prices    -> store
  indicators.py     # NEW  SMA/RSI/volatility/ATR/trend/52w-pos/drawdown/volume-ratio (numpy)
  patterns.py       # NEW  chart-pattern reads (cross, breakout, S/R, HH/LL, RSI zones)
  fundamentals.py   # NEW  deeper company scrape (NAV, P/B, reserve, EPS trend, div years) + fundamental_score
  score.py          # NEW  composite conviction score + signal (combines tech+fund+liquidity+risk)
  backtest.py       # NEW  forward-return validation of signals on stored history
  charts.py         # NEW  matplotlib renderers (price+SMA, sector pie, breadth, portfolio) -> PNG
api/
  core.py           # (existing) add re-exports for new modules
  routers/
    market.py       # (existing) unchanged
    portfolio.py    # (existing) unchanged
    reports.py      # (existing) unchanged
    analysis.py     # (existing) enrich /api/analysis with scores+patterns
    insights.py     # NEW  /api/history /api/indicators /api/patterns /api/score /api/backtest
                    #      + POST /api/snapshot/capture + POST /api/history/backfill
tests/
  conftest.py
  fixtures/{prices.html, company_gp.html, archive_gp.html}
  test_store.py test_history_parse.py test_indicators.py test_patterns.py
  test_fundamentals.py test_score.py test_backtest.py test_charts.py test_insights_api.py
requirements.txt    # + numpy, matplotlib
data/dse.db         # SQLite (git-ignored)
```

---

## PHASE A — Data foundation (history store + backfill + snapshot)

### Task 1: SQLite price store

**Files:** Create `tools/store.py`, `tests/__init__.py` (empty), `tests/conftest.py`, `tests/test_store.py`. Modify `.gitignore` (add `data/*.db`).

**Interfaces — Produces:**
- `connect(db_path=None) -> sqlite3.Connection` (Row factory)
- `init_db(db_path=None) -> None`
- `upsert_prices(rows: list[dict], db_path=None) -> int` — each row keys: `date,code,open,high,low,close,ycp,ltp,volume,value_mn,trades` (missing → NULL)
- `history(code: str, days: int = 420, db_path=None) -> list[dict]` — ascending by date
- `last_date(db_path=None) -> str | None`
- `codes_with_history(min_rows: int = 60, db_path=None) -> list[str]`

- [ ] **Step 1: conftest with a temp-DB fixture**

`tests/conftest.py`:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import pytest

@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "test.db")
```

- [ ] **Step 2: Write the failing test**

`tests/test_store.py`:
```python
import store

def test_upsert_and_history(db):
    store.init_db(db)
    rows = [
        {"date": "2026-06-24", "code": "GP", "close": 250, "ltp": 250, "high": 252, "low": 249, "ycp": 248, "volume": 1000, "value_mn": 5.0},
        {"date": "2026-06-25", "code": "GP", "close": 255, "ltp": 255, "high": 256, "low": 250, "ycp": 250, "volume": 1200, "value_mn": 6.0},
    ]
    assert store.upsert_prices(rows, db) == 2
    # idempotent upsert (same keys updates, no dup)
    rows[1]["close"] = 256
    store.upsert_prices(rows, db)
    h = store.history("GP", db_path=db)
    assert [r["date"] for r in h] == ["2026-06-24", "2026-06-25"]
    assert h[-1]["close"] == 256
    assert store.last_date(db) == "2026-06-25"
```

- [ ] **Step 3: Run it — expect FAIL** (`ModuleNotFoundError: store` / no functions)

Run: `cd tests && ../.venv/Scripts/python -m pytest test_store.py -v`

- [ ] **Step 4: Implement `tools/store.py`**

```python
"""Local SQLite OHLC store for DSE shares. Stdlib only."""
from __future__ import annotations
import os, sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "dse.db"
COLS = ["date", "code", "open", "high", "low", "close", "ycp", "ltp", "volume", "value_mn", "trades"]

def connect(db_path=None):
    p = str(db_path or DB_PATH)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    return con

def init_db(db_path=None):
    with connect(db_path) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS prices(
            date TEXT, code TEXT, open REAL, high REAL, low REAL, close REAL,
            ycp REAL, ltp REAL, volume REAL, value_mn REAL, trades REAL,
            PRIMARY KEY(date, code))""")
        con.execute("CREATE INDEX IF NOT EXISTS ix_code_date ON prices(code, date)")

def upsert_prices(rows, db_path=None):
    init_db(db_path)
    cols = ",".join(COLS)
    ph = ",".join("?" * len(COLS))
    upd = ",".join(f"{c}=excluded.{c}" for c in COLS if c not in ("date", "code"))
    sql = f"INSERT INTO prices({cols}) VALUES({ph}) ON CONFLICT(date,code) DO UPDATE SET {upd}"
    n = 0
    with connect(db_path) as con:
        for r in rows:
            con.execute(sql, [r.get(c) for c in COLS]); n += 1
    return n

def history(code, days=420, db_path=None):
    with connect(db_path) as con:
        cur = con.execute(
            "SELECT * FROM prices WHERE code=? ORDER BY date DESC LIMIT ?", (code.upper(), days))
        return [dict(r) for r in cur.fetchall()][::-1]

def last_date(db_path=None):
    with connect(db_path) as con:
        r = con.execute("SELECT MAX(date) d FROM prices").fetchone()
        return r["d"] if r else None

def codes_with_history(min_rows=60, db_path=None):
    with connect(db_path) as con:
        cur = con.execute("SELECT code FROM prices GROUP BY code HAVING COUNT(*)>=?", (min_rows,))
        return [r["code"] for r in cur.fetchall()]
```

- [ ] **Step 5: Run — expect PASS.** Add `data/*.db` to `.gitignore`.
- [ ] **Step 6: Commit** — `git add tools/store.py tests .gitignore && git commit -m "feat(store): sqlite OHLC price store"`

---

### Task 2: Historical backfill from `day_end_archive.php`

**Files:** Create `tools/history.py`, `tests/fixtures/archive_gp.html`, `tests/test_history_parse.py`.

**Interfaces:**
- Consumes: `dse.fetch`, `dse._num`, `store.upsert_prices`.
- Produces: `parse_archive(html: str) -> list[dict]` (rows with `date,code,open,high,low,close,ycp,ltp,volume,value_mn,trades`); `fetch_archive(code, start, end) -> list[dict]`; `backfill(code, start, end, db_path=None) -> int`; CLI `python tools/history.py --code GP --start 2023-01-01 --end 2026-06-26` and `--all`.

- [ ] **Step 1: Capture the fixture (one-time, network).** First inspect the form's real input `name=` attributes, then save a sample:

Run:
```
cd tools
../.venv/Scripts/python -c "import dse; open('../tests/fixtures/archive_gp.html','w',encoding='utf-8').write(dse.fetch('https://www.dsebd.org/day_end_archive.php?startDate=2026-05-01&endDate=2026-06-26&inst=GP&archive=data','fx_archive',0))"
```
Open the saved file; confirm a table whose header row contains `Date` and `LTP`/`CLOSEP` and the GP rows. (If the param names differ from `startDate/endDate/inst/archive`, read them off the form and adjust `fetch_archive` accordingly — the parser keys off header text, not params, so only `fetch_archive` URL needs the right names.)

- [ ] **Step 2: Write the failing test**

`tests/test_history_parse.py`:
```python
from pathlib import Path
import history

FX = Path(__file__).parent / "fixtures"

def test_parse_archive_rows():
    rows = history.parse_archive((FX / "archive_gp.html").read_text(encoding="utf-8"))
    assert len(rows) >= 5
    r = rows[0]
    assert {"date", "code", "close", "high", "low", "volume"} <= r.keys()
    assert r["code"]  # non-empty
    assert all(isinstance(x["close"], (float, type(None))) for x in rows)
```

- [ ] **Step 3: Run — expect FAIL.**

- [ ] **Step 4: Implement `tools/history.py`** (parser keys off header names so it survives column reordering)

```python
"""Backfill historical OHLC from dsebd.org/day_end_archive.php into the store."""
from __future__ import annotations
import argparse, sys
from datetime import date
from bs4 import BeautifulSoup
import dse, store

ARCHIVE = "https://www.dsebd.org/day_end_archive.php"
_MAP = {"date": "date", "trading code": "code", "ltp": "ltp", "ltp*": "ltp",
        "high": "high", "low": "low", "openp": "open", "openp*": "open", "open": "open",
        "closep": "close", "closep*": "close", "close": "close", "ycp": "ycp", "ycp*": "ycp",
        "trade": "trades", "value (mn)": "value_mn", "value": "value_mn", "volume": "volume"}

def parse_archive(html):
    soup = BeautifulSoup(html, "html.parser")
    for tbl in soup.find_all("table"):
        head = tbl.find("tr")
        if not head:
            continue
        cols = [th.get_text(strip=True).lower() for th in head.find_all(["th", "td"])]
        if "date" not in cols or not any("code" in c for c in cols):
            continue
        idx = {i: _MAP[c] for i, c in enumerate(cols) if c in _MAP}
        rows = []
        for tr in head.find_next_siblings("tr"):
            cells = tr.find_all("td")
            if len(cells) < len(cols):
                continue
            rec = {"open": None, "high": None, "low": None, "close": None,
                   "ycp": None, "ltp": None, "volume": None, "value_mn": None, "trades": None}
            for i, c in enumerate(cells):
                key = idx.get(i)
                if not key:
                    continue
                txt = c.get_text(strip=True)
                rec[key] = txt if key in ("date", "code") else dse._num(txt)
            if rec.get("date") and rec.get("code"):
                rec["code"] = rec["code"].upper()
                rows.append(rec)
        if rows:
            return rows
    return []

def fetch_archive(code, start, end):
    url = f"{ARCHIVE}?startDate={start}&endDate={end}&inst={code.upper()}&archive=data"
    return parse_archive(dse.fetch(url, f"archive_{code}_{start}_{end}", ttl=0))

def backfill(code, start, end, db_path=None):
    rows = fetch_archive(code, start, end)
    return store.upsert_prices(rows, db_path)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code"); ap.add_argument("--all", action="store_true")
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--end", default=date.today().isoformat())
    a = ap.parse_args()
    codes = [r["code"] for r in dse.get_prices()] if a.all else [a.code]
    total = 0
    for c in codes:
        try:
            n = backfill(c, a.start, a.end); total += n
            print(f"{c}: {n}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"{c}: ERROR {e}", file=sys.stderr)
    print(total)

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test — expect PASS.** Then a live smoke (network): `cd tools && ../.venv/Scripts/python history.py --code GP --start 2026-01-01 --end 2026-06-26` prints a positive number; `../.venv/Scripts/python -c "import store;print(len(store.history('GP')))"` > 50.
- [ ] **Step 6: Commit** — `feat(history): backfill OHLC from DSE day-end archive`

---

### Task 3: Daily EOD snapshot from live prices

**Files:** Create `tools/snapshot.py`, `tests/test_snapshot.py`.

**Interfaces:**
- Consumes: `dse.get_prices`, `store.upsert_prices`.
- Produces: `capture(db_path=None, today=None) -> int` (maps each live row → store row for today's date; `close=ltp`); CLI `python tools/snapshot.py`.

- [ ] **Step 1: Write the failing test**

`tests/test_snapshot.py`:
```python
import snapshot, store, dse

def test_capture_writes_today(db, monkeypatch):
    monkeypatch.setattr(dse, "get_prices", lambda ttl=60: [
        {"code": "GP", "ltp": 257, "high": 258, "low": 255, "ycp": 256, "value_mn": 50, "volume": 1000, "trades": 100}])
    n = snapshot.capture(db_path=db, today="2026-06-26")
    assert n == 1
    h = store.history("GP", db_path=db)
    assert h[-1]["close"] == 257 and h[-1]["date"] == "2026-06-26"
```

- [ ] **Step 2: Run — FAIL. Step 3: Implement**

```python
"""Capture today's EOD snapshot from the live price page into the store."""
from __future__ import annotations
from datetime import date
import dse, store

def capture(db_path=None, today=None):
    d = today or date.today().isoformat()
    rows = []
    for r in dse.get_prices():
        rows.append({"date": d, "code": r["code"], "open": None,
                     "high": r.get("high"), "low": r.get("low"),
                     "close": r.get("ltp"), "ycp": r.get("ycp"), "ltp": r.get("ltp"),
                     "volume": r.get("volume"), "value_mn": r.get("value_mn"), "trades": r.get("trades")})
    return store.upsert_prices(rows, db_path)

if __name__ == "__main__":
    print(capture())
```

- [ ] **Step 4: Run — PASS. Step 5: Commit** — `feat(snapshot): daily EOD capture into store`

---

## PHASE B — Accuracy (indicators, patterns, fundamentals, score)

### Task 4: Technical indicators

**Files:** Create `tools/indicators.py`, `tests/test_indicators.py`. Modify `requirements.txt` (+`numpy>=2.0`).

**Interfaces:**
- Produces: `sma(vals,n)`, `rsi(vals,n=14)`, `volatility(vals,n=20)` (annualised %), `atr(hist,n=14)`, `max_drawdown(vals)`, `volume_ratio(hist,n=20)`, `pos_52w(hist)`, `trend(hist)`→`"UP"|"DOWN"|"SIDE"`, and `compute(hist) -> dict` with keys `last_close,sma20,sma50,sma200,rsi14,vol20,atr14,drawdown,vol_ratio,pos_52w,trend,sma_cross` (`sma_cross` ∈ `"GOLDEN"|"DEATH"|None`). `hist` = list of store rows (ascending). All return `None` when insufficient data.

- [ ] **Step 1: install numpy** — `.venv/Scripts/python -m pip install "numpy>=2.0"` and add to `requirements.txt`.

- [ ] **Step 2: Write the failing test** (deterministic series)

`tests/test_indicators.py`:
```python
import indicators as ind

def _h(closes):
    return [{"close": c, "high": c + 1, "low": c - 1, "volume": 100} for c in closes]

def test_sma():
    assert ind.sma([1, 2, 3, 4, 5], 5) == 3.0
    assert ind.sma([1, 2], 5) is None

def test_rsi_all_up_is_100():
    assert round(ind.rsi(list(range(1, 30)), 14)) == 100

def test_trend_up():
    h = _h([i for i in range(1, 80)])
    assert ind.trend(h) == "UP"

def test_compute_keys():
    h = _h([100 + (i % 5) for i in range(1, 60)])
    c = ind.compute(h)
    assert {"sma20", "rsi14", "trend", "pos_52w", "vol_ratio"} <= c.keys()
```

- [ ] **Step 3: Run — FAIL. Step 4: Implement `tools/indicators.py`**

```python
"""Technical indicators over store OHLC history (numpy)."""
from __future__ import annotations
import numpy as np

def _closes(hist):
    return [r["close"] for r in hist if r.get("close") is not None]

def sma(vals, n):
    if len(vals) < n:
        return None
    return round(float(np.mean(vals[-n:])), 4)

def rsi(vals, n=14):
    if len(vals) <= n:
        return None
    d = np.diff(np.array(vals, dtype=float))
    gain = np.where(d > 0, d, 0.0); loss = np.where(d < 0, -d, 0.0)
    ag = gain[:n].mean(); al = loss[:n].mean()
    for i in range(n, len(d)):
        ag = (ag * (n - 1) + gain[i]) / n
        al = (al * (n - 1) + loss[i]) / n
    if al == 0:
        return 100.0
    rs = ag / al
    return round(100 - 100 / (1 + rs), 2)

def volatility(vals, n=20):
    if len(vals) < n + 1:
        return None
    r = np.diff(np.log(np.array(vals[-(n + 1):], dtype=float)))
    return round(float(r.std(ddof=1) * np.sqrt(252) * 100), 2)

def atr(hist, n=14):
    if len(hist) < n + 1:
        return None
    trs = []
    for i in range(1, len(hist)):
        h, l, pc = hist[i].get("high"), hist[i].get("low"), hist[i - 1].get("close")
        if None in (h, l, pc):
            continue
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return round(float(np.mean(trs[-n:])), 4) if len(trs) >= n else None

def max_drawdown(vals):
    if len(vals) < 2:
        return None
    a = np.array(vals, dtype=float); peak = np.maximum.accumulate(a)
    return round(float(((a - peak) / peak).min() * 100), 2)

def volume_ratio(hist, n=20):
    vols = [r["volume"] for r in hist if r.get("volume")]
    if len(vols) < n + 1:
        return None
    avg = np.mean(vols[-(n + 1):-1])
    return round(float(vols[-1] / avg), 2) if avg else None

def pos_52w(hist):
    h = hist[-252:] if len(hist) >= 252 else hist
    closes = _closes(h)
    if len(closes) < 2:
        return None
    lo, hi = min(closes), max(closes)
    return round((closes[-1] - lo) / (hi - lo) * 100, 1) if hi > lo else None

def trend(hist):
    c = _closes(hist)
    s20, s50 = sma(c, 20), sma(c, 50)
    if s20 is None or s50 is None:
        return "SIDE"
    if s20 > s50 * 1.01:
        return "UP"
    if s20 < s50 * 0.99:
        return "DOWN"
    return "SIDE"

def compute(hist):
    c = _closes(hist)
    s20, s50 = sma(c, 20), sma(c, 50)
    prev = _closes(hist[:-1])
    p20, p50 = sma(prev, 20), sma(prev, 50)
    cross = None
    if None not in (s20, s50, p20, p50):
        if p20 <= p50 and s20 > s50:
            cross = "GOLDEN"
        elif p20 >= p50 and s20 < s50:
            cross = "DEATH"
    return {"last_close": c[-1] if c else None, "sma20": s20, "sma50": s50,
            "sma200": sma(c, 200), "rsi14": rsi(c), "vol20": volatility(c),
            "atr14": atr(hist), "drawdown": max_drawdown(c), "vol_ratio": volume_ratio(hist),
            "pos_52w": pos_52w(hist), "trend": trend(hist), "sma_cross": cross}
```

- [ ] **Step 5: Run — PASS. Step 6: Commit** — `feat(indicators): SMA/RSI/vol/ATR/trend/52w/drawdown`

---

### Task 5: Chart-pattern analysis

**Files:** Create `tools/patterns.py`, `tests/test_patterns.py`.

**Interfaces:**
- Consumes: `indicators` (`compute` output) + history.
- Produces: `support_resistance(hist, lookback=60) -> (support, resistance)`; `analyze(hist, ind) -> {summary:str, signals:list[str], support:float|None, resistance:float|None, bias:"BULLISH"|"BEARISH"|"NEUTRAL"}`.

- [ ] **Step 1: Write the failing test**

`tests/test_patterns.py`:
```python
import patterns, indicators as ind

def _h(cl):
    return [{"close": c, "high": c + 1, "low": c - 1, "volume": 100} for c in cl]

def test_uptrend_bullish():
    h = _h(list(range(50, 130)))
    a = patterns.analyze(h, ind.compute(h))
    assert a["bias"] == "BULLISH"
    assert a["resistance"] is not None
    assert any("trend" in s.lower() or "sma" in s.lower() for s in a["signals"])

def test_overbought_flag():
    h = _h(list(range(1, 40)))  # straight up -> RSI ~100
    a = patterns.analyze(h, ind.compute(h))
    assert any("overbought" in s.lower() for s in a["signals"])
```

- [ ] **Step 2: Run — FAIL. Step 3: Implement `tools/patterns.py`**

```python
"""Human-readable chart-pattern reads from history + indicators."""
from __future__ import annotations

def support_resistance(hist, lookback=60):
    h = hist[-lookback:]
    lows = [r["low"] for r in h if r.get("low") is not None]
    highs = [r["high"] for r in h if r.get("high") is not None]
    return (round(min(lows), 2) if lows else None, round(max(highs), 2) if highs else None)

def analyze(hist, ind):
    sig, score = [], 0
    last = ind.get("last_close")
    s20, s50, rsi, tr, cross = ind.get("sma20"), ind.get("sma50"), ind.get("rsi14"), ind.get("trend"), ind.get("sma_cross")
    sup, res = support_resistance(hist)

    if tr == "UP":
        sig.append("Uptrend (SMA20 > SMA50)"); score += 2
    elif tr == "DOWN":
        sig.append("Downtrend (SMA20 < SMA50)"); score -= 2
    else:
        sig.append("Sideways / range-bound")
    if cross == "GOLDEN":
        sig.append("Golden cross (SMA20 crossed above SMA50)"); score += 2
    elif cross == "DEATH":
        sig.append("Death cross (SMA20 crossed below SMA50)"); score -= 2
    if last and s20:
        sig.append(f"Price {'above' if last > s20 else 'below'} SMA20")
        score += 1 if last > s20 else -1
    if rsi is not None:
        if rsi >= 70:
            sig.append(f"RSI {rsi} - overbought"); score -= 1
        elif rsi <= 30:
            sig.append(f"RSI {rsi} - oversold (possible bounce)"); score += 1
        else:
            sig.append(f"RSI {rsi} - neutral")
    if res and last and last >= res * 0.99:
        sig.append(f"Testing/!breaking resistance {res}"); score += 1
    if sup and last and last <= sup * 1.01:
        sig.append(f"Near support {sup}")
    pos = ind.get("pos_52w")
    if pos is not None:
        sig.append(f"{pos}% up its 52-week range")
    bias = "BULLISH" if score >= 2 else "BEARISH" if score <= -2 else "NEUTRAL"
    summary = f"{bias.title()} setup: " + "; ".join(sig[:4]) + "."
    return {"summary": summary, "signals": sig, "support": sup, "resistance": res, "bias": bias}
```

- [ ] **Step 4: Run — PASS. Step 5: Commit** — `feat(patterns): chart-pattern analysis from history`

---

### Task 6: Deeper fundamentals + fundamental score

**Files:** Create `tools/fundamentals.py`, `tests/test_fundamentals.py`. Ensure `tests/fixtures/company_gp.html` exists (re-fetch if missing, same as the existing scraper fixture).

**Interfaces:**
- Consumes: `dse.parse_company`, `dse.fetch`, `dse.COMPANY_URL`, `dse._num`.
- Produces: `parse_more(html, code) -> dict` adding `nav, reserve_surplus_mn, eps_history(list[float]), dividend_years(int)`; `enrich_fundamentals(code, ltp) -> dict` (base `parse_company` + `parse_more` + derived `pb`, `div_yield`, `eps_positive`, `eps_growth`); `fundamental_score(f) -> (score_0_100, list[str] notes)`.

- [ ] **Step 1: Capture/confirm fixture.** If absent: `cd tools && ../.venv/Scripts/python -c "import dse;open('../tests/fixtures/company_gp.html','w',encoding='utf-8').write(dse.fetch(dse.COMPANY_URL.format(code='GP'),'fx_gp',0))"`.

- [ ] **Step 2: Write the failing test**

`tests/test_fundamentals.py`:
```python
from pathlib import Path
import fundamentals as fnd

FX = Path(__file__).parent / "fixtures"

def test_parse_more_gp():
    m = fnd.parse_more((FX / "company_gp.html").read_text(encoding="utf-8"), "GP")
    assert "nav" in m and "dividend_years" in m
    assert m["dividend_years"] >= 1

def test_fundamental_score_range():
    s, notes = fnd.fundamental_score(
        {"pe": 12.0, "pb": 2.0, "div_yield": 8.0, "dividend_years": 10,
         "market_category": "A", "eps_positive": True, "eps_growth": True})
    assert 0 <= s <= 100 and s >= 60  # quality name scores well
    assert isinstance(notes, list)
```

- [ ] **Step 3: Run — FAIL. Step 4: Implement `tools/fundamentals.py`**

```python
"""Deeper company fundamentals + a transparent 0-100 fundamental score."""
from __future__ import annotations
import re
from bs4 import BeautifulSoup
import dse

def parse_more(html, code):
    soup = BeautifulSoup(html, "html.parser")
    cells = [c.get_text(" ", strip=True) for c in soup.find_all(["td", "th"])]

    def after(label):
        for i, c in enumerate(cells):
            if c.startswith(label):
                tail = c[len(label):].strip(" :")
                if tail:
                    return tail
                if i + 1 < len(cells):
                    return cells[i + 1]
        return None

    text = soup.get_text(" ", strip=True)
    eps_hist = [float(x) for x in re.findall(r"-?\d+\.\d+", (after("EPS") or ""))][:8]
    div = after("Dividend") or ""
    years = len(re.findall(r"\d{4}", div))
    return {"nav": dse._num(after("NAV per Share") or after("NAV")),
            "reserve_surplus_mn": dse._num(after("Reserve") or ""),
            "eps_history": eps_hist, "dividend_years": years}

def enrich_fundamentals(code, ltp):
    html = dse.fetch(dse.COMPANY_URL.format(code=code), f"company_{code}", ttl=3600)
    base = dse.parse_company(html, code)
    more = parse_more(html, code)
    f = {**base, **more}
    f["pb"] = round(ltp / f["nav"], 2) if f.get("nav") and ltp else None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", f.get("dividend_history") or "")
    f["div_yield"] = round(float(m.group(1)) / 100 * f["face_value"] / ltp * 100, 2) if (m and f.get("face_value") and ltp) else None
    eps = f.get("eps_basic")
    f["eps_positive"] = bool(eps and eps > 0)
    hist = f.get("eps_history") or []
    f["eps_growth"] = bool(len(hist) >= 2 and hist[0] > hist[-1])
    return f

def fundamental_score(f):
    s, notes = 50, []
    pe = f.get("pe")
    if pe is not None:
        if pe <= 0:
            s -= 20; notes.append("negative/zero P/E")
        elif pe < 10:
            s += 15; notes.append("low P/E")
        elif pe < 20:
            s += 8
        elif pe > 40:
            s -= 15; notes.append("very high P/E")
    pb = f.get("pb")
    if pb is not None:
        if pb < 1.5:
            s += 8; notes.append("below 1.5x book")
        elif pb > 5:
            s -= 8; notes.append("rich vs book")
    dy = f.get("div_yield") or 0
    if dy >= 5:
        s += 10; notes.append(f"div yield {dy}%")
    elif dy == 0:
        s -= 8; notes.append("no dividend")
    if (f.get("dividend_years") or 0) >= 5:
        s += 8; notes.append("consistent payer")
    if f.get("eps_positive"):
        s += 5
    else:
        s -= 10; notes.append("EPS not positive")
    cat = (f.get("market_category") or "").upper()
    if cat == "A":
        s += 8
    elif cat in ("B", "N"):
        s -= 5; notes.append(f"Cat {cat}")
    elif cat == "Z":
        s -= 25; notes.append("Cat Z - serious concern")
    return max(0, min(100, s)), notes
```

- [ ] **Step 5: Run — PASS. Step 6: Commit** — `feat(fundamentals): deeper scrape + fundamental score`

---

### Task 7: Composite conviction score + signal

**Files:** Create `tools/score.py`, `tests/test_score.py`.

**Interfaces:**
- Consumes: `indicators.compute`, `patterns.analyze`, `fundamentals.fundamental_score`, `dse._pct_change`.
- Produces: `technical_score(ind, patt) -> (0..100, notes)`; `composite(row, ind, patt, fund_score) -> {score:int, signal:str, technical:int, fundamental:int, breakdown:list[str]}` where `signal ∈ BUY|WATCH|HOLD|AVOID`. Hard risk filters override score (illiquid `value_mn<0.5`→AVOID; daily crash ≤ −7%→AVOID; Cat Z→cap WATCH).

- [ ] **Step 1: Write the failing test**

`tests/test_score.py`:
```python
import score

IND_UP = {"trend": "UP", "rsi14": 60, "last_close": 100, "sma20": 95, "sma50": 90,
          "sma_cross": "GOLDEN", "vol_ratio": 1.5, "pos_52w": 70, "drawdown": -8}
PATT = {"bias": "BULLISH"}

def test_strong_buy():
    r = {"value_mn": 50, "ltp": 100, "ycp": 98}
    out = score.composite(r, IND_UP, PATT, 75)
    assert out["signal"] in ("BUY", "WATCH")
    assert out["score"] >= 60

def test_illiquid_is_avoid():
    r = {"value_mn": 0.1, "ltp": 5, "ycp": 5}
    out = score.composite(r, IND_UP, PATT, 80)
    assert out["signal"] == "AVOID"

def test_crash_is_avoid():
    r = {"value_mn": 50, "ltp": 90, "ycp": 100}  # -10%
    out = score.composite(r, IND_UP, PATT, 80)
    assert out["signal"] == "AVOID"
```

- [ ] **Step 2: Run — FAIL. Step 3: Implement `tools/score.py`**

```python
"""Composite conviction score: technical + fundamental + liquidity, with hard risk gates."""
from __future__ import annotations
import dse

def technical_score(ind, patt):
    s, notes = 50, []
    if ind.get("trend") == "UP":
        s += 12; notes.append("uptrend")
    elif ind.get("trend") == "DOWN":
        s -= 12; notes.append("downtrend")
    if ind.get("sma_cross") == "GOLDEN":
        s += 8; notes.append("golden cross")
    elif ind.get("sma_cross") == "DEATH":
        s -= 8; notes.append("death cross")
    rsi = ind.get("rsi14")
    if rsi is not None:
        if rsi >= 75:
            s -= 8; notes.append("overbought")
        elif rsi <= 30:
            s += 6; notes.append("oversold")
    last, s20 = ind.get("last_close"), ind.get("sma20")
    if last and s20:
        s += 6 if last > s20 else -6
    vr = ind.get("vol_ratio")
    if vr and vr >= 1.5:
        s += 6; notes.append(f"volume {vr}x avg")
    pos = ind.get("pos_52w")
    if pos is not None and pos >= 95:
        s -= 4; notes.append("near 52w high")
    if patt.get("bias") == "BULLISH":
        s += 6
    elif patt.get("bias") == "BEARISH":
        s -= 6
    return max(0, min(100, s)), notes

def composite(row, ind, patt, fund_score):
    tech, tnotes = technical_score(ind, patt)
    score = round(0.55 * tech + 0.45 * (fund_score if fund_score is not None else 50))
    pct = dse._pct_change(row)
    val = row.get("value_mn") or 0
    # hard risk gates
    if val < 0.5:
        return {"score": score, "signal": "AVOID", "technical": tech, "fundamental": fund_score,
                "breakdown": tnotes + ["illiquid (<0.5mn) - hard exit"]}
    if pct <= -7:
        return {"score": score, "signal": "AVOID", "technical": tech, "fundamental": fund_score,
                "breakdown": tnotes + [f"crash {pct:.1f}% - falling knife"]}
    if pct >= 9.5:
        sig = "WATCH"  # at upper circuit; don't chase
    elif score >= 68:
        sig = "BUY"
    elif score >= 55:
        sig = "WATCH"
    elif score >= 40:
        sig = "HOLD"
    else:
        sig = "AVOID"
    return {"score": score, "signal": sig, "technical": tech, "fundamental": fund_score,
            "breakdown": tnotes}
```

- [ ] **Step 4: Run — PASS. Step 5: Commit** — `feat(score): composite conviction score + signal`

---

## PHASE C — Validation (backtest)

### Task 8: Backtest signals on stored history

**Files:** Create `tools/backtest.py`, `tests/test_backtest.py`.

**Interfaces:**
- Consumes: `store.history`, `indicators.compute`, `patterns.analyze`, `score.composite` (fundamentals omitted in backtest → pass `fund_score=None`, point-in-time only uses price history).
- Produces: `evaluate(code, horizon=20, db_path=None) -> dict{by_signal:{SIGNAL:{n,win_rate,avg_ret}}}`; `evaluate_many(codes, horizon=20) -> aggregated`; CLI `python tools/backtest.py --horizon 20 [--code GP]`.

- [ ] **Step 1: Write the failing test** (synthetic monotonic-up history → BUY signals win)

`tests/test_backtest.py`:
```python
import backtest, store

def test_evaluate_uptrend(db):
    rows = [{"date": f"2026-01-{i:02d}", "code": "UP", "close": 100 + i,
             "high": 101 + i, "low": 99 + i, "ycp": 99 + i, "ltp": 100 + i,
             "volume": 1000, "value_mn": 50} for i in range(1, 29)]
    store.upsert_prices(rows, db)
    out = backtest.evaluate("UP", horizon=3, db_path=db)
    assert "by_signal" in out
    total = sum(v["n"] for v in out["by_signal"].values())
    assert total > 0
```

- [ ] **Step 2: Run — FAIL. Step 3: Implement `tools/backtest.py`**

```python
"""Walk-forward backtest: did past signals lead to positive forward returns?"""
from __future__ import annotations
import argparse, sys
import store, indicators as ind, patterns, score, dse

def evaluate(code, horizon=20, db_path=None):
    hist = store.history(code, days=2000, db_path=db_path)
    buckets = {}
    for i in range(60, len(hist) - horizon):
        window = hist[:i + 1]
        row = {"value_mn": window[-1].get("value_mn") or 0,
               "ltp": window[-1].get("close"), "ycp": window[-1].get("ycp")}
        ic = ind.compute(window)
        pt = patterns.analyze(window, ic)
        sig = score.composite(row, ic, pt, None)["signal"]
        entry = window[-1].get("close")
        exit_ = hist[i + horizon].get("close")
        if not entry or not exit_:
            continue
        ret = (exit_ - entry) / entry * 100
        b = buckets.setdefault(sig, {"n": 0, "wins": 0, "sum": 0.0})
        b["n"] += 1; b["sum"] += ret; b["wins"] += 1 if ret > 0 else 0
    by = {s: {"n": b["n"], "win_rate": round(b["wins"] / b["n"] * 100, 1),
              "avg_ret": round(b["sum"] / b["n"], 2)} for s, b in buckets.items() if b["n"]}
    return {"code": code, "horizon": horizon, "by_signal": by}

def evaluate_many(codes, horizon=20, db_path=None):
    agg = {}
    for c in codes:
        for s, v in evaluate(c, horizon, db_path).get("by_signal", {}).items():
            a = agg.setdefault(s, {"n": 0, "wins": 0.0, "sum": 0.0})
            a["n"] += v["n"]; a["wins"] += v["win_rate"] * v["n"] / 100; a["sum"] += v["avg_ret"] * v["n"]
    return {"horizon": horizon, "by_signal": {s: {"n": a["n"],
            "win_rate": round(a["wins"] / a["n"] * 100, 1) if a["n"] else 0,
            "avg_ret": round(a["sum"] / a["n"], 2) if a["n"] else 0} for s, a in agg.items()}}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--horizon", type=int, default=20); ap.add_argument("--code")
    a = ap.parse_args()
    codes = [a.code] if a.code else store.codes_with_history(min_rows=120)
    import json; print(json.dumps(evaluate_many(codes, a.horizon), indent=2))

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run — PASS. Step 5: Commit** — `feat(backtest): walk-forward signal validation`

---

## PHASE D — Reporting (charts + analytics + report v2)

### Task 9: Chart renderers (matplotlib)

**Files:** Create `tools/charts.py`, `tests/test_charts.py`. Modify `requirements.txt` (+`matplotlib>=3.9`).

**Interfaces:**
- Produces: `price_chart(hist, ind, out_path)`, `sector_pie(weights:dict, out_path)`, `breadth_bar(breadth:dict, out_path)`, `portfolio_alloc(positions:list, out_path)` — each writes a PNG and returns `out_path`.

- [ ] **Step 1: install matplotlib** — `.venv/Scripts/python -m pip install "matplotlib>=3.9"` + add to `requirements.txt`.

- [ ] **Step 2: Write the failing test**

`tests/test_charts.py`:
```python
import os, charts, indicators as ind

def test_price_chart_png(tmp_path):
    h = [{"date": f"d{i}", "close": 100 + i, "high": 101 + i, "low": 99 + i, "volume": 100} for i in range(60)]
    p = tmp_path / "c.png"
    charts.price_chart(h, ind.compute(h), str(p))
    assert os.path.getsize(p) > 1000  # real PNG bytes

def test_sector_pie_png(tmp_path):
    p = tmp_path / "s.png"
    charts.sector_pie({"Textile": 3, "Bank": 2}, str(p))
    assert os.path.getsize(p) > 1000
```

- [ ] **Step 3: Run — FAIL. Step 4: Implement `tools/charts.py`** (Agg backend, dark theme to match PDF)

```python
"""Matplotlib chart renderers -> PNG, embedded in the PDF. Headless (Agg)."""
from __future__ import annotations
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

NAVY = "#102a43"; BLUE = "#3b82f6"; GREEN = "#16a34a"; AMBER = "#f59e0b"; GREY = "#94a3b8"

def _save(fig, path):
    fig.savefig(path, dpi=110, bbox_inches="tight", facecolor="white"); plt.close(fig); return path

def price_chart(hist, ind, out_path):
    closes = [r["close"] for r in hist if r.get("close") is not None]
    fig, ax = plt.subplots(figsize=(6, 2.2))
    ax.plot(closes, color=NAVY, lw=1.4, label="Close")
    def ma(n):
        return [sum(closes[i - n + 1:i + 1]) / n if i >= n - 1 else None for i in range(len(closes))]
    if len(closes) >= 20:
        ax.plot(ma(20), color=BLUE, lw=1.0, label="SMA20")
    if len(closes) >= 50:
        ax.plot(ma(50), color=AMBER, lw=1.0, label="SMA50")
    ax.legend(fontsize=6, loc="upper left", frameon=False)
    ax.tick_params(labelsize=6); ax.set_xticks([]); ax.grid(alpha=0.15)
    return _save(fig, out_path)

def sector_pie(weights, out_path):
    fig, ax = plt.subplots(figsize=(3.2, 3.2))
    ax.pie(list(weights.values()), labels=list(weights.keys()),
           autopct="%1.0f%%", textprops={"fontsize": 7},
           colors=plt.cm.tab20.colors)
    return _save(fig, out_path)

def breadth_bar(breadth, out_path):
    fig, ax = plt.subplots(figsize=(3.2, 2.0))
    ax.bar(["Adv", "Dec", "Unch"],
           [breadth.get("adv", 0), breadth.get("dec", 0),
            max(0, breadth.get("total", 0) - breadth.get("adv", 0) - breadth.get("dec", 0))],
           color=[GREEN, "#dc2626", GREY])
    ax.tick_params(labelsize=7)
    return _save(fig, out_path)

def portfolio_alloc(positions, out_path):
    labels = [p["code"] for p in positions]
    vals = [p.get("mval") or 0 for p in positions]
    fig, ax = plt.subplots(figsize=(3.2, 3.2))
    ax.pie(vals, labels=labels, autopct="%1.0f%%", textprops={"fontsize": 7}, colors=plt.cm.Set2.colors)
    return _save(fig, out_path)
```

- [ ] **Step 5: Run — PASS. Step 6: Commit** — `feat(charts): matplotlib renderers for the PDF`

---

### Task 10: Portfolio analytics

**Files:** Modify `tools/report.py` (add `portfolio_analytics`). Create `tests/test_portfolio_analytics.py`.

**Interfaces:**
- Consumes: `report.load_portfolio` output + `fundamentals.enrich_fundamentals` (sector, div).
- Produces (in `tools/report.py`): `portfolio_analytics(port) -> {weights:list[(code,pct)], sectors:dict[str,float], top_weight:(code,pct), dividend_income:float, notes:list[str]}`.

- [ ] **Step 1: Write the failing test**

`tests/test_portfolio_analytics.py`:
```python
import report

def test_analytics(monkeypatch):
    port = {"positions": [
        {"code": "A", "mval": 60000, "sector": "Textile", "quantity": 100, "div_per_share": 2.0},
        {"code": "B", "mval": 40000, "sector": "Bank", "quantity": 50, "div_per_share": 0.0}],
        "market": 100000, "invested": 110000, "pnl": -10000, "ret": -9.09}
    a = report.portfolio_analytics(port)
    assert a["top_weight"][0] == "A" and round(a["top_weight"][1]) == 60
    assert "Textile" in a["sectors"]
```

- [ ] **Step 2: Run — FAIL. Step 3: Implement `portfolio_analytics` in `tools/report.py`**

```python
def portfolio_analytics(port):
    total = port.get("market") or sum(p.get("mval") or 0 for p in port["positions"]) or 1
    weights = sorted(((p["code"], round((p.get("mval") or 0) / total * 100, 1))
                      for p in port["positions"]), key=lambda x: -x[1])
    sectors = {}
    for p in port["positions"]:
        sectors[p.get("sector") or "Unknown"] = round(
            sectors.get(p.get("sector") or "Unknown", 0) + (p.get("mval") or 0) / total * 100, 1)
    income = sum((p.get("quantity") or 0) * (p.get("div_per_share") or 0) for p in port["positions"])
    notes = []
    if weights and weights[0][1] > 40:
        notes.append(f"Concentrated: {weights[0][0]} is {weights[0][1]}% of book")
    big_sector = max(sectors.items(), key=lambda x: x[1], default=(None, 0))
    if big_sector[1] > 50:
        notes.append(f"Sector heavy: {big_sector[0]} {big_sector[1]}%")
    return {"weights": weights, "sectors": sectors,
            "top_weight": weights[0] if weights else (None, 0),
            "dividend_income": round(income, 2), "notes": notes}
```
(Engineer: in `load_portfolio`, also set per-position `div_per_share` from `fundamentals.enrich_fundamentals` — latest dividend % × face_value/100 — so income is real. Reuse the existing `enrich`/`_div_yield` plumbing.)

- [ ] **Step 4: Run — PASS. Step 5: Commit** — `feat(report): portfolio analytics (weights/sectors/income)`

---

### Task 11: Report v2 — scores, patterns, charts, analytics

**Files:** Modify `tools/report.py` (`select` enrichment + `build_pdf` sections + new candidate block with chart). Create `tests/test_report_v2.py`.

**Interfaces:**
- Consumes: `store.history`, `indicators.compute`, `patterns.analyze`, `fundamentals.enrich_fundamentals`+`fundamental_score`, `score.composite`, `charts.*`, `portfolio_analytics`.
- Produces: in `select()`, each buy/watch candidate gains `score, signal, technical, fundamental, pattern_summary, indicators` (history-driven; falls back to single-day when history absent). `build_pdf` adds: market breadth chart + sector pie; per-pick **price chart + pattern read + score bar**; portfolio page with allocation pie + analytics; a **Backtest validation** summary page; the methodology page (kept). Ranking switches from value to **composite score desc**.

- [ ] **Step 1: Write the failing test** (PDF builds and is multi-page with charts)

`tests/test_report_v2.py`:
```python
from datetime import datetime
import report

def test_build_pdf_with_history(monkeypatch, tmp_path):
    # stub data so no network: one buy candidate with synthetic history
    hist = [{"date": f"d{i}", "close": 100 + i, "high": 101 + i, "low": 99 + i,
             "ycp": 99 + i, "ltp": 100 + i, "volume": 100, "value_mn": 50} for i in range(60)]
    monkeypatch.setattr(report, "select", lambda b, w: {
        "regime": "BULLISH", "breadth": {"adv": 2, "dec": 1, "total": 3, "value_mn": 10.0},
        "buy": [{"code": "UP", "ltp": 160, "pct": 1.0, "value_mn": 50, "reason": "x",
                 "pe": 10, "div_yield": 5, "category": "A", "sector": "Bank",
                 "range_52w": "100 - 160", "levels": {"support": 99, "resistance": 161, "stop": 94, "target": 170},
                 "score": 72, "signal": "BUY", "technical": 70, "fundamental": 75,
                 "pattern_summary": "Bullish: uptrend; golden cross.", "history": hist}],
        "watch": [], "avoid": []})
    monkeypatch.setattr(report, "load_portfolio", lambda p: None)
    p = report.build_pdf(report.select(6, 6), None, datetime(2026, 6, 26, 17, 0))
    assert p.endswith(".pdf")
    import os; assert os.path.getsize(p) > 5000
```

- [ ] **Step 2: Run — FAIL.**

- [ ] **Step 3: Implement.** In `tools/report.py`:
  1. Add imports: `import store, indicators, patterns, fundamentals, score, charts` and a temp dir for chart PNGs (use `tempfile.mkdtemp()`).
  2. In `enrich(row)`: after current fundamentals, load `h = store.history(row["code"])`; if `len(h) >= 30`: `ic = indicators.compute(h)`, `pt = patterns.analyze(h, ic)`, `f = fundamentals.enrich_fundamentals(row["code"], row["ltp"])`, `fs,_ = fundamentals.fundamental_score(f)`, `comp = score.composite(row, ic, pt, fs)`; attach `score,signal,technical,fundamental,pattern_summary=pt["summary"],indicators=ic,history=h`. Else attach `score=None` and keep the legacy `_rate` tag.
  3. In `select()`: rank `buy` by `score` desc (fallback `value_mn`); keep `BUY-WATCH` gate but prefer `signal=="BUY"` when score present.
  4. New `candidate_block_v2(pdf, i, r)`: render the existing text block **plus** a score line (`Score 72/100  ·  tech 70  fund 75  ·  BUY`) and, if `r.get("history")`, `charts.price_chart(...)` to a temp PNG and `pdf.image(png, w=120)`, then `pdf.multi_cell(... r["pattern_summary"])`.
  5. New sections in `build_pdf`: after the KPI band add `charts.breadth_bar` + (buy-candidate) `charts.sector_pie` images side by side; portfolio page adds `charts.portfolio_alloc` + `portfolio_analytics` notes; add a "BACKTEST (last run)" page reading the most recent `backtest.evaluate_many` result if a cached JSON exists at `reports/backtest.json` (skip gracefully if absent).
  6. Clean up the temp PNG dir at the end of `build_pdf`.

- [ ] **Step 4: Run — PASS.** Live end-to-end: `.venv/Scripts/python tools/report.py --buy 6 --watch 6 --investor B10526 --cash 36600.98` → open PDF, confirm charts + scores + pattern reads render.
- [ ] **Step 5: Commit** — `feat(report): v2 with scores, pattern reads, charts, portfolio analytics`

---

## PHASE E — API + automation

### Task 12: Insight API endpoints

**Files:** Create `api/routers/insights.py`. Modify `api/core.py` (re-export `store, indicators, patterns, fundamentals, score, backtest, snapshot, history`), `api/main.py` (include router), `api/routers/analysis.py` (attach `score/signal/pattern_summary` to each pick). Create `tests/test_insights_api.py`.

**Interfaces — Produces routes:**
- `GET /api/history?code=&days=` → store rows
- `GET /api/indicators?code=` → `indicators.compute(store.history(code))`
- `GET /api/patterns?code=` → `patterns.analyze(...)`
- `GET /api/score?code=` → composite for one code; `GET /api/score?limit=` ranked market (codes with history)
- `GET /api/backtest?horizon=&code=` → backtest result
- `POST /api/snapshot/capture` → `{captured:n}`
- `POST /api/history/backfill?code=&start=&end=` → `{stored:n}`

- [ ] **Step 1: Write the failing test** (use temp DB via env override; monkeypatch `store.DB_PATH`)

`tests/test_insights_api.py`:
```python
from fastapi.testclient import TestClient
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.main import app
from api.core import store

client = TestClient(app)

def test_history_and_indicators(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "t.db")
    store.upsert_prices([{"date": f"2026-01-{i:02d}", "code": "GP", "close": 100 + i,
                          "high": 101 + i, "low": 99 + i, "ycp": 99 + i, "ltp": 100 + i,
                          "volume": 100, "value_mn": 5} for i in range(1, 40)])
    assert client.get("/api/history?code=GP").json()  # non-empty
    ind = client.get("/api/indicators?code=GP").json()
    assert "rsi14" in ind
```

- [ ] **Step 2: Run — FAIL. Step 3: Implement `api/routers/insights.py`**

```python
from fastapi import APIRouter, HTTPException, Query
from api.core import store, indicators, patterns, score, backtest, snapshot, history, dse, fundamentals

router = APIRouter(prefix="/api", tags=["insights"])

@router.get("/history")
def get_history(code: str, days: int = 420):
    return store.history(code, days)

@router.get("/indicators")
def get_ind(code: str):
    h = store.history(code)
    if len(h) < 30:
        raise HTTPException(404, "not enough history - backfill first")
    return indicators.compute(h)

@router.get("/patterns")
def get_patterns(code: str):
    h = store.history(code)
    if len(h) < 30:
        raise HTTPException(404, "not enough history")
    return patterns.analyze(h, indicators.compute(h))

@router.get("/score")
def get_score(code: str | None = None, limit: int = Query(20, ge=1, le=100)):
    prices = {r["code"].upper(): r for r in dse.get_prices()}
    def one(c):
        h = store.history(c)
        if len(h) < 30:
            return None
        ic = indicators.compute(h); pt = patterns.analyze(h, ic)
        f = fundamentals.enrich_fundamentals(c, prices.get(c, {}).get("ltp"))
        fs, _ = fundamentals.fundamental_score(f)
        return {"code": c, **score.composite(prices.get(c, {}), ic, pt, fs),
                "pattern": pt["summary"]}
    if code:
        r = one(code.upper())
        if not r:
            raise HTTPException(404, "not enough history")
        return r
    out = [one(c) for c in store.codes_with_history(60)]
    out = [x for x in out if x]
    return sorted(out, key=lambda x: x["score"], reverse=True)[:limit]

@router.get("/backtest")
def get_backtest(horizon: int = 20, code: str | None = None):
    codes = [code] if code else store.codes_with_history(120)
    return backtest.evaluate_many(codes, horizon)

@router.post("/snapshot/capture")
def post_capture():
    return {"captured": snapshot.capture()}

@router.post("/history/backfill")
def post_backfill(code: str, start: str = "2023-01-01", end: str | None = None):
    from datetime import date
    return {"stored": history.backfill(code, start, end or date.today().isoformat())}
```
Add to `api/core.py`: `import store, indicators, patterns, fundamentals, score, backtest, snapshot, history` and extend `__all__`. Add `from api.routers import insights` + `app.include_router(insights.router)` in `api/main.py`.

- [ ] **Step 4: Run — PASS. Step 5: Commit** — `feat(api): insight endpoints (history/indicators/patterns/score/backtest)`

---

### Task 13: Automation + docs

**Files:** Create `tools/refresh.py` (one command: snapshot + optional backtest cache), `scripts/schedule_daily.ps1`. Modify `README.md`, `CLAUDE.md`, `.claude/commands/analysis.md`.

- [ ] **Step 1: `tools/refresh.py`** — runs `snapshot.capture()`, then `backtest.evaluate_many(store.codes_with_history(120), 20)` and writes `reports/backtest.json` (consumed by report v2). Print a one-line summary.
- [ ] **Step 2: `scripts/schedule_daily.ps1`** — registers a Windows Task Scheduler job that runs `\.venv\Scripts\python tools\refresh.py` at 17:00 daily:
```powershell
$action = New-ScheduledTaskAction -Execute "$PSScriptRoot\..\.venv\Scripts\python.exe" -Argument "tools\refresh.py" -WorkingDirectory "$PSScriptRoot\.."
$trigger = New-ScheduledTaskTrigger -Daily -At 5pm
Register-ScheduledTask -TaskName "DSE Daily Refresh" -Action $action -Trigger $trigger -Force
```
- [ ] **Step 3: Docs** — README: new "Accuracy engine" section (backfill once → `tools/history.py --all --start 2023-01-01`; daily `tools/refresh.py`; new API endpoints; scoring + backtest explanation). CLAUDE.md: add the new modules to Layout and the new commands. `analysis.md`: mention the report now includes scores, pattern reads, charts, and backtest validation.
- [ ] **Step 4: Commit** — `feat: daily refresh command, scheduler, docs`

---

## PHASE F — Quality gate

### Task 14: Full sweep + scraper hardening

**Files:** Modify `tools/dse.py` (`_get`: small retry/backoff + clearer error), `tests/conftest.py` (ensure `tools/` + repo root on path). Run the whole suite.

- [ ] **Step 1:** Add a 2-try retry with 1s backoff around the request in `dse._get` (keep the existing TLS-insecure fallback). Don't change signatures.
- [ ] **Step 2:** `cd tests && ../.venv/Scripts/python -m pytest -q` → all green (store, history-parse, indicators, patterns, fundamentals, score, backtest, charts, portfolio-analytics, report-v2, insights-api).
- [ ] **Step 3:** Live end-to-end sanity:
  - `.venv/Scripts/python tools/history.py --code GP --start 2026-01-01 --end 2026-06-26` (history > 50 rows)
  - `.venv/Scripts/python tools/refresh.py` (snapshot + backtest.json written)
  - `.venv/Scripts/python tools/report.py --buy 6 --watch 6 --investor B10526 --cash 36600.98` → PDF with charts + scores + pattern reads + backtest page
  - `.venv/Scripts/uvicorn api.main:app --port 8000` then `curl "localhost:8000/api/score?limit=10"` and `curl "localhost:8000/api/backtest?horizon=20&code=GP"`
- [ ] **Step 4: Commit** — `chore: scraper retry + full test sweep green`

---

## Verification (end-to-end)

1. **Tests:** `cd tests && ../.venv/Scripts/python -m pytest -q` → all pass, no network (fixtures + temp DB + synthetic series).
2. **Backfill:** `.venv/Scripts/python tools/history.py --code GP --start 2026-01-01 --end 2026-06-26` → store has GP OHLC; `/api/history?code=GP` returns rows; `/api/indicators?code=GP` returns RSI/SMA/trend.
3. **Scoring:** `/api/score?limit=10` returns a ranked list with `score, signal, technical, fundamental, pattern`. Spot-check a known uptrend name scores higher than a crasher.
4. **Backtest:** `/api/backtest?horizon=20&code=GP` returns per-signal `win_rate` + `avg_ret`; BUY's avg_ret/win_rate ≥ AVOID's (sanity that the score has signal).
5. **Report:** generated PDF includes — KPI band, breadth + sector charts, per-pick **price chart + pattern read + score**, portfolio allocation pie + concentration/sector/dividend-income notes, a backtest validation page, methodology. Matches iBroker portfolio value.
6. **Automation:** `tools/refresh.py` writes `reports/backtest.json`; scheduler task registered.

## Notes / risks

- **Archive params:** `day_end_archive.php` field names (`startDate/endDate/inst/archive`) must be confirmed off the live form in Task 2 Step 1; the parser itself is header-driven so only the request URL is sensitive.
- **History coverage:** indicators need ≥30 rows, SMA50/backtest need more. Backfill `--all` once (slow — ~1 req/code; run off-hours, cache TTL=0). Names with thin history fall back to the single-day `_rate` tag so nothing breaks.
- **numpy/matplotlib on Python 3.14:** both ship 3.14 wheels; if a wheel is missing, pin to the latest that provides one. matplotlib must use the `Agg` backend (set in `charts.py`).
- **Backtest is not advice:** it measures the rule set on past data with look-ahead-free windows; past performance ≠ future. Keep the disclaimer on every surface.
- **Performance:** `/api/score` (no code) and report ranking iterate all codes-with-history; acceptable for ~400 names with cached company pages, but consider a `limit`/`min_rows` guard (already in place).
