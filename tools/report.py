#!/usr/bin/env python3
"""Daily DSE report generator -> professional PDF.

Scans ALL Dhaka Stock Exchange shares, screens them into BUY / WATCHLIST / AVOID
with conditions + fundamentals, includes YOUR live portfolio P&L, and explains the
methodology. Writes a dated PDF into ./reports/.

Run from project root:
    .venv/Scripts/python tools/report.py
    .venv/Scripts/python tools/report.py --buy 8 --watch 8 --cash 36600.98 --investor B10526

Output: reports/DSE_Analysis_YYYY-MM-DD_HHMM_BDT.pdf

Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
from datetime import datetime

from fpdf import FPDF

from dse import get_prices, fetch, parse_company, COMPANY_URL, _rate, _pct_change

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(ROOT, "reports")

# palette
NAVY = (16, 42, 67)
NAVY2 = (23, 58, 92)
GREEN = (18, 122, 71)
RED = (190, 45, 45)
AMBER = (200, 130, 20)
GREY = (110, 120, 130)
LIGHT = (238, 242, 246)
WHITE = (255, 255, 255)
LINE = (210, 218, 226)


# --------------------------------------------------------------------------- #
# Text safety + formatting
# --------------------------------------------------------------------------- #
_UNI = {"—": "-", "–": "-", "‘": "'", "’": "'", "“": '"', "”": '"', "…": "...", "\xa0": " ", "৳": "Tk "}


def S(s) -> str:
    if s is None:
        return ""
    s = str(s)
    for k, v in _UNI.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def money(v):
    return "-" if v is None else f"{v:,.0f}"


def num(v, d=2):
    return "-" if v is None else f"{v:,.{d}f}"


# --------------------------------------------------------------------------- #
# Data: screen + enrich + portfolio
# --------------------------------------------------------------------------- #
def _div_yield(company, ltp):
    hist, fv = company.get("dividend_history"), company.get("face_value")
    if not hist or not fv or not ltp:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", hist)
    if not m:
        return None
    return round(float(m.group(1)) / 100.0 * fv / ltp * 100, 2)


def enrich(row):
    code = row["code"]
    out = dict(row)
    try:
        c = parse_company(fetch(COMPANY_URL.format(code=code), f"company_{code}", ttl=3600), code)
    except Exception:
        c = {}
    out["pe"] = c.get("pe")
    out["category"] = c.get("market_category")
    out["sector"] = c.get("sector")
    out["range_52w"] = c.get("moving_range_52w")
    out["div_yield"] = _div_yield(c, row.get("ltp"))
    return out


def _levels(row):
    high, low = row.get("high"), row.get("low")
    hi52 = None
    rng = row.get("range_52w")
    if rng:
        nums = re.findall(r"\d+(?:\.\d+)?", rng.replace(",", ""))
        if len(nums) >= 2:
            hi52 = float(nums[-1])
    return {"support": low, "resistance": high,
            "stop": round(low * 0.95, 1) if low else None,
            "target": hi52 or (round(high * 1.08, 1) if high else None)}


def select(buy_n, watch_n):
    rows = get_prices()
    rated = []
    for r in rows:
        tag, reason = _rate(r)
        r = dict(r); r["tag"], r["reason"], r["pct"] = tag, reason, _pct_change(r)
        rated.append(r)
    adv = sum(1 for x in rated if (x["pct"] or 0) > 0)
    dec = sum(1 for x in rated if (x["pct"] or 0) < 0)
    regime = "BULLISH" if adv > dec * 1.5 else "BEARISH" if dec > adv * 1.5 else "MIXED"

    buy = [r for r in rated if r["tag"] == "BUY-WATCH" and (r.get("value_mn") or 0) >= 5]
    buy.sort(key=lambda r: r.get("value_mn") or 0, reverse=True)
    buy = [enrich(r) for r in buy[:buy_n]]
    watch = [r for r in rated if r["tag"] in ("WATCH-DIP", "WAIT") and (r.get("value_mn") or 0) >= 3]
    watch.sort(key=lambda r: r.get("value_mn") or 0, reverse=True)
    watch = [enrich(r) for r in watch[:watch_n]]
    avoid_all = [r for r in rated if r["tag"] == "AVOID"]
    crash = sorted([r for r in avoid_all if (r.get("value_mn") or 0) >= 0.5], key=lambda r: r.get("pct") or 0)
    notrade = [r for r in avoid_all if (r.get("value_mn") or 0) < 0.5]
    for r in buy + watch:
        r["levels"] = _levels(r)
    return {"regime": regime,
            "breadth": {"adv": adv, "dec": dec, "total": len(rated),
                        "value_mn": round(sum(r.get("value_mn") or 0 for r in rated), 1)},
            "buy": buy, "watch": watch, "avoid": crash[:8] + notrade[:2]}


def load_portfolio(path):
    if not os.path.exists(path):
        return None
    holds = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("code"):
                holds.append({"code": row["code"].strip().upper(),
                              "quantity": float(row["quantity"]), "buy_price": float(row["buy_price"])})
    by = {r["code"].upper(): r for r in get_prices()}
    positions, invested, market = [], 0.0, 0.0
    for h in holds:
        r = by.get(h["code"])
        ltp = r["ltp"] if r else None
        cost = h["quantity"] * h["buy_price"]
        mval = h["quantity"] * ltp if ltp is not None else None
        pnl = (mval - cost) if mval is not None else None
        invested += cost; market += mval or 0
        positions.append({**h, "ltp": ltp, "cost": cost, "mval": mval, "pnl": pnl,
                          "pnl_pct": (pnl / cost * 100) if pnl is not None and cost else None,
                          "day": _pct_change(r) if r else None,
                          "tag": _rate(r)[0] if r else "NO-DATA",
                          "sector": (enrich(r).get("sector") if r else None)})
    return {"positions": positions, "invested": invested, "market": market,
            "pnl": market - invested, "ret": ((market - invested) / invested * 100) if invested else None}


# --------------------------------------------------------------------------- #
# PDF primitives
# --------------------------------------------------------------------------- #
class Report(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_y(8)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*NAVY)
        self.cell(0, 5, "DSE Daily Analysis")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 5, datetime.now().strftime("%d %b %Y"), align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*LINE)
        self.line(self.l_margin, 15, self.w - self.r_margin, 15)
        self.ln(6)

    def footer(self):
        self.set_y(-13)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*GREY)
        self.multi_cell(0, 4,
            "Data scraped from dsebd.org (delayed/EOD). Rule-based screen, educational only - "
            "NOT financial advice. Verify on the official DSE site before trading.   "
            f"Page {self.page_no()}", align="C")


def section(pdf, title, color=NAVY):
    pdf.ln(2)
    pdf.set_fill_color(*color)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "  " + S(title), fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def kpi_band(pdf, items):
    """items: list of (label, value, color). Draws equal-width boxes."""
    n = len(items)
    gap = 3
    w = (pdf.w - pdf.l_margin - pdf.r_margin - gap * (n - 1)) / n
    x0, y0 = pdf.get_x(), pdf.get_y()
    for i, (label, value, color) in enumerate(items):
        x = x0 + i * (w + gap)
        pdf.set_xy(x, y0)
        pdf.set_fill_color(*LIGHT)
        pdf.set_draw_color(*LINE)
        pdf.rect(x, y0, w, 16, "DF")
        pdf.set_xy(x + 2, y0 + 2.5)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*GREY)
        pdf.cell(w - 4, 4, S(label.upper()))
        pdf.set_xy(x + 2, y0 + 7.5)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*color)
        pdf.cell(w - 4, 6, S(value))
    pdf.set_xy(x0, y0 + 16 + 2)


def table(pdf, headers, widths, aligns, rows, zebra=True):
    """rows: list of list-of-cells; a cell is str or (str, rgb_color)."""
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_fill_color(*NAVY)
    pdf.set_text_color(*WHITE)
    pdf.set_draw_color(*LINE)
    for h, w, a in zip(headers, widths, aligns):
        pdf.cell(w, 7, S(h), border=0, align=a, fill=True)
    pdf.ln(7)
    pdf.set_font("Helvetica", "", 7.5)
    for ri, row in enumerate(rows):
        if zebra and ri % 2:
            pdf.set_fill_color(*LIGHT); fill = True
        else:
            pdf.set_fill_color(*WHITE); fill = True
        for cell, w, a in zip(row, widths, aligns):
            if isinstance(cell, tuple):
                text, col = cell
            else:
                text, col = cell, (30, 35, 40)
            pdf.set_text_color(*col)
            pdf.cell(w, 6.5, S(str(text)), border=0, align=a, fill=fill)
        pdf.ln(6.5)
    pdf.set_draw_color(*LINE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + sum(widths), pdf.get_y())


def pnl_color(v):
    return GREEN if (v or 0) > 0 else RED if (v or 0) < 0 else GREY


# --------------------------------------------------------------------------- #
# Sections
# --------------------------------------------------------------------------- #
def cover(pdf, data, port, investor, cash):
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, pdf.w, 30, "F")
    pdf.set_xy(pdf.l_margin, 8)
    pdf.set_font("Helvetica", "B", 19)
    pdf.set_text_color(*WHITE)
    pdf.cell(0, 9, "DSE DAILY MARKET ANALYSIS", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(200, 215, 230)
    label = f"Dhaka Stock Exchange   |   {datetime.now().strftime('%A, %d %B %Y  %H:%M')} BDT"
    if investor:
        label += f"   |   Investor: {investor}"
    pdf.cell(0, 6, S(label))
    pdf.ln(20)

    reg = data["regime"]; b = data["breadth"]
    rc = GREEN if reg == "BULLISH" else RED if reg == "BEARISH" else AMBER
    items = [("Market", reg, rc),
             ("Advances / Declines", f"{b['adv']} / {b['dec']}", GREEN if b['adv'] > b['dec'] else RED),
             ("Value Traded (mn)", money(b["value_mn"]), NAVY)]
    if port:
        items += [("Portfolio Value", money(port["market"]), NAVY),
                  ("Unrealized P&L", money(port["pnl"]), pnl_color(port["pnl"])),
                  ("Return", f"{num(port['ret'],2)}%", pnl_color(port["pnl"]))]
        if cash:
            items.append(("Total Equity", money(port["market"] + cash), NAVY))
    # split into rows of up to 4
    for i in range(0, len(items), 4):
        kpi_band(pdf, items[i:i + 4])


def portfolio_section(pdf, port, cash):
    section(pdf, "YOUR PORTFOLIO  -  live profit & loss", NAVY2)
    headers = ["Trading Code", "Qty", "Avg", "LTP", "Cost", "Mkt Value", "P&L", "P&L%", "Day%", "Signal"]
    widths = [30, 15, 17, 16, 24, 24, 22, 15, 13, 14]
    aligns = ["L", "R", "R", "R", "R", "R", "R", "R", "R", "C"]
    rows = []
    for p in port["positions"]:
        rows.append([
            p["code"], num(p["quantity"], 0), num(p["buy_price"]), num(p["ltp"]),
            money(p["cost"]), money(p["mval"]),
            (money(p["pnl"]), pnl_color(p["pnl"])),
            (num(p["pnl_pct"], 2), pnl_color(p["pnl"])),
            (num(p["day"], 2), pnl_color(p["day"])),
            p["tag"],
        ])
    table(pdf, headers, widths, aligns, rows)
    # totals
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*NAVY)
    pdf.cell(sum(widths[:4]), 7, "TOTAL", align="L")
    pdf.cell(widths[4], 7, money(port["invested"]), align="R")
    pdf.cell(widths[5], 7, money(port["market"]), align="R")
    pdf.set_text_color(*pnl_color(port["pnl"]))
    pdf.cell(widths[6], 7, money(port["pnl"]), align="R")
    pdf.cell(widths[7], 7, num(port["ret"], 2), align="R")
    pdf.ln(9)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*GREY)
    line = (f"Invested Tk {money(port['invested'])}   Market Tk {money(port['market'])}   "
            f"Unrealized P&L Tk {money(port['pnl'])} ({num(port['ret'],2)}%)")
    if cash:
        line += f"   Cash Tk {money(cash)}   Total Equity Tk {money(port['market'] + cash)}"
    pdf.multi_cell(0, 5, S(line), new_x="LMARGIN", new_y="NEXT")
    # quick read on positions
    worst = min(port["positions"], key=lambda p: p.get("pnl_pct") or 0, default=None)
    if worst and (worst.get("pnl_pct") or 0) < -5:
        pdf.set_text_color(*RED)
        pdf.multi_cell(0, 5, S(f"Biggest drag: {worst['code']} {num(worst['pnl_pct'],1)}% - review thesis vs. average-down."),
                       new_x="LMARGIN", new_y="NEXT")


def candidate_block(pdf, i, r, kind):
    lv = r.get("levels") or _levels(r)
    pct = r.get("pct") or 0
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*NAVY)
    pdf.cell(70, 6, S(f"{i}. {r['code']}"))
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*pnl_color(pct))
    pdf.cell(0, 6, f"{pct:+.1f}%   LTP {num(r.get('ltp'))}", align="R", new_x="LMARGIN", new_y="NEXT")
    flags = []
    if r.get("pe") is not None and r["pe"] > 40:
        flags.append("HIGH P/E")
    if (r.get("category") or "").upper() in ("B", "N", "Z"):
        flags.append(f"Cat {r['category']}")
    if (r.get("div_yield") or 0) == 0:
        flags.append("no div")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*GREY)
    meta = (f"P/E {num(r.get('pe'),1)}   Div~{num(r.get('div_yield'),1)}%   Cat {r.get('category') or '-'}   "
            f"Vol {num(r.get('value_mn'),1)}mn   {r.get('sector') or ''}")
    if flags:
        meta += "    [!] " + ", ".join(flags)
    pdf.multi_cell(0, 4.6, S(meta), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(40, 45, 50)
    pdf.multi_cell(0, 4.6, S(f"Why: {r.get('reason','')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*NAVY)
    if kind == "buy":
        plan = (f"Plan: entry on dip {num(lv['support'])} or break above {num(lv['resistance'])}.  "
                f"Stop {num(lv['stop'])}.  Target {num(lv['target'])} (52w high).  52w {r.get('range_52w') or '-'}.")
    else:
        plan = (f"Watch: pullback to {num(lv['support'])} or confirm above {num(lv['resistance'])} on volume.  "
                f"52w {r.get('range_52w') or '-'}.")
    pdf.multi_cell(0, 4.6, S(plan), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*LINE)
    pdf.line(pdf.l_margin, pdf.get_y() + 1.5, pdf.w - pdf.r_margin, pdf.get_y() + 1.5)
    pdf.ln(3.5)


def avoid_section(pdf, avoid):
    section(pdf, "AVOID / RISK", RED)
    headers = ["Trading Code", "Change", "Reason"]
    widths = [34, 24, 132]
    rows = []
    for r in avoid:
        chg = "no trade" if (r.get("value_mn") or 0) < 0.5 else f"{(r.get('pct') or 0):+.1f}%"
        rows.append([r["code"], (chg, pnl_color(r.get("pct"))), r.get("reason", "")])
    table(pdf, headers, widths, ["L", "R", "L"], rows)


def methodology(pdf):
    pdf.add_page()
    section(pdf, "HOW SHARES ARE PICKED  (methodology)", NAVY2)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(40, 45, 50)
    intro = ("Every traded share is scored from the day's price + volume only (a fast technical "
             "screen), then buy/watch candidates are enriched with fundamentals. Tags:")
    pdf.multi_cell(0, 5, S(intro), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    items = [
        ("BUY-WATCH", GREEN, "Up 1.5-7% on real volume (>=5mn Tk) and closing in the upper part of the day's "
                             "range - strength with room before the +10% circuit. These become Buy candidates."),
        ("WATCH-DIP", (40, 90, 160), "Down 2-7% on volume (>=3mn Tk) - a possible support test; wait for a base, do not catch blindly."),
        ("WAIT", AMBER, "Up >=7% - near the upper circuit / overbought. Do not chase today; wait for a pullback."),
        ("AVOID", RED, "Down >=7% (falling knife near lower circuit) OR illiquid (<0.5mn Tk traded - hard to exit)."),
        ("HOLD / NEUTRAL", GREY, "Small moves (-2% to +1.5%) or low conviction - no action."),
    ]
    for tag, col, desc in items:
        pdf.set_font("Helvetica", "B", 9); pdf.set_text_color(*col)
        pdf.cell(34, 5.5, S(tag))
        pdf.set_font("Helvetica", "", 9); pdf.set_text_color(40, 45, 50)
        pdf.multi_cell(0, 5.5, S(desc), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(0.5)
    pdf.ln(2)
    section(pdf, "RISK FLAGS on candidates", NAVY2)
    pdf.set_font("Helvetica", "", 9); pdf.set_text_color(40, 45, 50)
    for f in [
        "HIGH P/E  - price/earnings above 40: expensive / speculative.",
        "Cat B / N / Z  - weaker DSE category (Z = serious concern, irregular dividend).",
        "no div  - no recent cash dividend.",
        "Entry / Stop / Target  - dip-entry = day's low; stop = 5% below low; target = 52-week high.",
    ]:
        pdf.multi_cell(0, 5.5, S("- " + f), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 9); pdf.set_text_color(*RED)
    pdf.multi_cell(0, 5,
        S("This is a rule-based technical screen for research only - NOT financial advice. BD micro-caps "
          "can be manipulated; always confirm with fundamentals, news and the official DSE site before trading."),
        new_x="LMARGIN", new_y="NEXT")


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
def build_pdf(data, port, when, investor=None, cash=0.0):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    pdf = Report()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()
    cover(pdf, data, port, investor, cash)

    if port and port["positions"]:
        portfolio_section(pdf, port, cash)

    section(pdf, "BUY CANDIDATES  -  momentum on volume", GREEN)
    if data["buy"]:
        for i, r in enumerate(data["buy"], 1):
            candidate_block(pdf, i, r, "buy")
    else:
        pdf.set_font("Helvetica", "I", 9); pdf.set_text_color(*GREY)
        pdf.multi_cell(0, 6, "No clean buy setups today. Stay patient.", new_x="LMARGIN", new_y="NEXT")

    section(pdf, "WATCHLIST  -  wait for the right entry", NAVY)
    if data["watch"]:
        for i, r in enumerate(data["watch"], 1):
            candidate_block(pdf, i, r, "watch")
    else:
        pdf.set_font("Helvetica", "I", 9); pdf.set_text_color(*GREY)
        pdf.multi_cell(0, 6, "Nothing on watch today.", new_x="LMARGIN", new_y="NEXT")

    avoid_section(pdf, data["avoid"])
    methodology(pdf)

    fname = f"DSE_Analysis_{when.strftime('%Y-%m-%d_%H%M')}_BDT.pdf"
    path = os.path.join(REPORTS_DIR, fname)
    pdf.output(path)
    return path


def main():
    p = argparse.ArgumentParser(description="Generate dated DSE analysis PDF")
    p.add_argument("--buy", type=int, default=6)
    p.add_argument("--watch", type=int, default=6)
    p.add_argument("--portfolio", default=os.path.join("data", "portfolio.csv"))
    p.add_argument("--cash", type=float, default=0.0, help="ledger/cash balance for total equity")
    p.add_argument("--investor", default=None, help="investor code shown on the cover")
    args = p.parse_args()

    when = datetime.now()
    data = select(args.buy, args.watch)
    port = load_portfolio(args.portfolio)
    path = build_pdf(data, port, when, investor=args.investor, cash=args.cash)
    print(path)


if __name__ == "__main__":
    main()
