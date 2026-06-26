#!/usr/bin/env python3
"""Daily DSE report generator -> PDF.

Scans ALL Dhaka Stock Exchange shares, screens them, picks a shortlist of
BUY candidates and a WATCHLIST (each with entry / stop / target conditions and
fundamentals), then writes a dated PDF into ./reports/.

Run from project root:
    .venv/Scripts/python tools/report.py
    .venv/Scripts/python tools/report.py --buy 6 --watch 6

Output file:  reports/DSE_Analysis_YYYY-MM-DD_HHMM_BDT.pdf

Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice.
"""
from __future__ import annotations

import argparse
import os
import re
from datetime import datetime

from fpdf import FPDF

# dse.py sits next to this file; running `python tools/report.py` puts tools/ on sys.path
from dse import get_prices, fetch, parse_company, COMPANY_URL, _rate, _pct_change

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(ROOT, "reports")


# --------------------------------------------------------------------------- #
# Selection + enrichment
# --------------------------------------------------------------------------- #
def _div_yield(company: dict, ltp):
    """Approx cash dividend yield % from latest dividend (% of face value)."""
    hist = company.get("dividend_history")
    fv = company.get("face_value")
    if not hist or not fv or not ltp:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", hist)
    if not m:
        return None
    cash_per_share = float(m.group(1)) / 100.0 * fv
    return round(cash_per_share / ltp * 100, 2)


def enrich(row: dict) -> dict:
    """Add fundamentals + trade levels to a screened row."""
    code = row["code"]
    out = dict(row)
    try:
        html = fetch(COMPANY_URL.format(code=code), f"company_{code}", ttl=3600)
        c = parse_company(html, code)
    except Exception:
        c = {}
    out["pe"] = c.get("pe")
    out["eps"] = c.get("eps_basic")
    out["category"] = c.get("market_category")
    out["sector"] = c.get("sector")
    out["range_52w"] = c.get("moving_range_52w")
    out["div_yield"] = _div_yield(c, row.get("ltp"))
    return out


def _levels(row: dict) -> dict:
    """Entry/stop/target from today's high/low + 52-week high."""
    ltp, high, low = row.get("ltp"), row.get("high"), row.get("low")
    hi52 = None
    rng = row.get("range_52w")
    if rng:
        nums = re.findall(r"\d+(?:\.\d+)?", rng.replace(",", ""))
        if len(nums) >= 2:
            hi52 = float(nums[-1])
    return {
        "support": low,
        "resistance": high,
        "stop": round(low * 0.95, 1) if low else None,
        "target": hi52 or (round(high * 1.08, 1) if high else None),
    }


def select(buy_n: int, watch_n: int):
    rows = get_prices()
    rated = []
    for r in rows:
        tag, reason = _rate(r)
        r = dict(r)
        r["tag"], r["reason"], r["pct"] = tag, reason, _pct_change(r)
        rated.append(r)

    adv = sum(1 for x in rated if (x["pct"] or 0) > 0)
    dec = sum(1 for x in rated if (x["pct"] or 0) < 0)
    regime = "BULLISH" if adv > dec * 1.5 else "BEARISH" if dec > adv * 1.5 else "MIXED"

    buy = [r for r in rated if r["tag"] == "BUY-WATCH" and (r.get("value_mn") or 0) >= 5]
    buy.sort(key=lambda r: r.get("value_mn") or 0, reverse=True)
    buy = [enrich(r) for r in buy[:buy_n]]

    # watchlist: dips on volume (potential entry) + strong-but-overbought (wait for pullback)
    watch = [r for r in rated if r["tag"] in ("WATCH-DIP", "WAIT") and (r.get("value_mn") or 0) >= 3]
    watch.sort(key=lambda r: r.get("value_mn") or 0, reverse=True)
    watch = [enrich(r) for r in watch[:watch_n]]

    avoid_all = [r for r in rated if r["tag"] == "AVOID"]
    crash = sorted([r for r in avoid_all if (r.get("value_mn") or 0) >= 0.5],
                   key=lambda r: r.get("pct") or 0)
    notrade = [r for r in avoid_all if (r.get("value_mn") or 0) < 0.5]
    avoid = crash[:6] + notrade[:2]  # real decliners first, then a couple inactive shells

    return {
        "regime": regime,
        "breadth": {"adv": adv, "dec": dec, "total": len(rated),
                    "value_mn": round(sum(r.get("value_mn") or 0 for r in rated), 1)},
        "buy": buy, "watch": watch, "avoid": avoid,
    }


# --------------------------------------------------------------------------- #
# PDF rendering
# --------------------------------------------------------------------------- #
NAVY = (15, 40, 75)
GREEN = (20, 120, 50)
RED = (165, 30, 30)
GREY = (90, 90, 90)


class Report(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*GREY)
        self.cell(0, 6, "DSE Daily Analysis", align="L")
        self.cell(0, 6, f"Page {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*GREY)
        self.multi_cell(0, 4,
            "Data scraped from dsebd.org (delayed/EOD). Rule-based screen, educational only "
            "- NOT financial advice. Verify on the official DSE site before trading.",
            align="C")


def _fmt(v, dash="-"):
    return dash if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v))


_UNI = {"—": "-", "–": "-", "‘": "'", "’": "'",
        "“": '"', "”": '"', "…": "...", " ": " "}


def S(s) -> str:
    """Make text safe for the latin-1 core PDF font."""
    if s is None:
        return ""
    s = str(s)
    for k, v in _UNI.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def candidate_block(pdf: Report, i: int, r: dict, kind: str):
    lv = _levels(r)
    pct = r.get("pct") or 0
    # title line
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 7, f"{i}. {r['code']}", new_x="LMARGIN", new_y="NEXT")
    # price line
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*(GREEN if pct >= 0 else RED))
    pdf.cell(40, 5, f"LTP {_fmt(r.get('ltp'))}  ({pct:+.1f}%)")
    pdf.set_text_color(*GREY)
    flags = []
    pe = r.get("pe")
    if pe is not None and pe > 40:
        flags.append("HIGH P/E")
    if (r.get("category") or "").upper() in ("B", "N", "Z"):
        flags.append(f"Cat {r['category']} risk")
    if (r.get("div_yield") or 0) == 0:
        flags.append("no div")
    flag_txt = ("   [!] " + ", ".join(flags)) if flags else ""
    meta = (f"P/E {_fmt(r.get('pe'))}   Div~{_fmt(r.get('div_yield'))}%   "
            f"Cat {r.get('category') or '-'}   Vol {_fmt(r.get('value_mn'))}mn   "
            f"{r.get('sector') or ''}{flag_txt}")
    pdf.multi_cell(0, 5, S(meta), new_x="LMARGIN", new_y="NEXT")
    # why
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5, S(f"Why: {r.get('reason','')}"), new_x="LMARGIN", new_y="NEXT")
    # plan
    if kind == "buy":
        plan = (f"Plan: entry on dip near {_fmt(lv['support'])} or break above {_fmt(lv['resistance'])}. "
                f"Stop {_fmt(lv['stop'])}. Target {_fmt(lv['target'])} (52w high). "
                f"52w range {r.get('range_52w') or '-'}.")
    else:
        plan = (f"Watch: wait pullback to {_fmt(lv['support'])} or confirmation above {_fmt(lv['resistance'])} "
                f"on volume. Don't chase. 52w range {r.get('range_52w') or '-'}.")
    pdf.set_text_color(*NAVY)
    pdf.multi_cell(0, 5, S(plan), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(220, 220, 220)
    pdf.line(pdf.l_margin, pdf.get_y() + 1, pdf.w - pdf.r_margin, pdf.get_y() + 1)
    pdf.ln(3)


def section_title(pdf: Report, text: str, color=NAVY):
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*color)
    pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*color)
    pdf.set_line_width(0.4)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(2)


def build_pdf(data: dict, when: datetime) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    pdf = Report()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 12, "DSE Daily Market Analysis", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 6, f"Dhaka Stock Exchange  |  {when.strftime('%A, %d %B %Y  %H:%M')} BDT",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Market snapshot box
    b = data["breadth"]
    reg = data["regime"]
    reg_color = GREEN if reg == "BULLISH" else RED if reg == "BEARISH" else GREY
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*reg_color)
    pdf.cell(0, 7, f"Market: {reg}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 6,
        f"Advances {b['adv']}  /  Declines {b['dec']}   (of {b['total']} traded)    "
        f"Total value traded: {b['value_mn']} mn BDT",
        new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(*GREY)
    pdf.multi_cell(0, 5,
        f"Scanned {b['total']} shares. {len(data['buy'])} buy candidates, "
        f"{len(data['watch'])} watchlist, {len(data['avoid'])} flagged avoid.",
        new_x="LMARGIN", new_y="NEXT")

    # BUY
    section_title(pdf, "BUY CANDIDATES", GREEN)
    if data["buy"]:
        for i, r in enumerate(data["buy"], 1):
            candidate_block(pdf, i, r, "buy")
    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(*GREY)
        pdf.multi_cell(0, 6, "No clean buy setups today. Stay patient.", new_x="LMARGIN", new_y="NEXT")

    # WATCHLIST
    section_title(pdf, "WATCHLIST", NAVY)
    if data["watch"]:
        for i, r in enumerate(data["watch"], 1):
            candidate_block(pdf, i, r, "watch")
    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(*GREY)
        pdf.multi_cell(0, 6, "Nothing on watch today.", new_x="LMARGIN", new_y="NEXT")

    # AVOID
    section_title(pdf, "AVOID / RISK", RED)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(0, 0, 0)
    if data["avoid"]:
        for r in data["avoid"]:
            chg = "no trade" if (r.get("value_mn") or 0) < 0.5 else f"{(r.get('pct') or 0):+.1f}%"
            pdf.multi_cell(0, 5,
                S(f"- {r['code']}  ({chg})  -  {r.get('reason','')}"),
                new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 5, "None flagged.", new_x="LMARGIN", new_y="NEXT")

    fname = f"DSE_Analysis_{when.strftime('%Y-%m-%d_%H%M')}_BDT.pdf"
    path = os.path.join(REPORTS_DIR, fname)
    pdf.output(path)
    return path


def main():
    p = argparse.ArgumentParser(description="Generate dated DSE analysis PDF")
    p.add_argument("--buy", type=int, default=6, help="number of buy candidates")
    p.add_argument("--watch", type=int, default=6, help="number of watchlist names")
    args = p.parse_args()

    when = datetime.now()
    data = select(args.buy, args.watch)
    path = build_pdf(data, when)
    print(path)


if __name__ == "__main__":
    main()
