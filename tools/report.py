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
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime

from fpdf import FPDF

from dse import get_prices, fetch, parse_company, COMPANY_URL, _rate, _pct_change
import backtest
import charts
import fundamentals
import indicators
import patterns
import prediction
import score
import store

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
BENGALI_FONT_PATH = os.path.join(ROOT, "assets", "fonts", "NotoSansBengali.ttf")
DOC_FONT = "NotoBengali" if os.path.exists(BENGALI_FONT_PATH) else "Helvetica"


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
    if DOC_FONT == "Helvetica":
        return s.encode("latin-1", "replace").decode("latin-1")
    return s


def setup_fonts(pdf):
    if DOC_FONT != "Helvetica":
        for style in ("", "B", "I", "BI"):
            try:
                pdf.add_font(DOC_FONT, style, BENGALI_FONT_PATH)
            except RuntimeError:
                pass


def doc_font(pdf, style="", size=9):
    pdf.set_font(DOC_FONT, style, size)


def pred_bn(label):
    return {
        "BULLISH_CONTINUATION": "বুলিশ কন্টিনিউ",
        "BULLISH_BIAS": "বুলিশ ঝোঁক",
        "RANGE / UNCERTAIN": "রেঞ্জ / অনিশ্চিত",
        "PULLBACK_RISK": "পুলব্যাক ঝুঁকি",
        "BEARISH_CONTINUATION": "বিয়ারিশ কন্টিনিউ ঝুঁকি",
    }.get(label or "", label or "-")


def signal_bn(label):
    return {
        "BUY": "BUY-WATCH",
        "WATCH": "WATCH",
        "BUY-WATCH": "BUY-WATCH",
        "WATCH-DIP": "WATCH-DIP",
        "WAIT": "WAIT",
        "HOLD": "HOLD",
        "NEUTRAL": "NEUTRAL",
        "AVOID": "AVOID",
        "NO-DATA": "NO-DATA",
    }.get(label or "", label or "-")


def confidence_bn(value):
    return {"HIGH": "উচ্চ", "MEDIUM": "মাঝারি", "LOW": "কম"}.get(value or "", value or "-")


def horizon_bn(value):
    if value == "next 1-5 sessions":
        return "পরবর্তী ১-৫ সেশন"
    return value or "-"


def candle_label_bn(label):
    return {
        "NO_CANDLE": "ক্যান্ডেল ডাটা নেই",
        "FLAT": "ফ্ল্যাট ক্যান্ডেল",
        "STRONG_BULLISH_CLOSE": "শক্তিশালী বুলিশ ক্লোজ",
        "STRONG_BEARISH_CLOSE": "শক্তিশালী বিয়ারিশ ক্লোজ",
        "LOWER_WICK_REJECTION": "নিচের উইক রিজেকশন",
        "UPPER_WICK_REJECTION": "উপরের উইক রিজেকশন",
        "INDECISION": "দ্বিধা / ছোট বডি",
        "BULLISH_CANDLE": "বুলিশ ক্যান্ডেল",
        "BEARISH_CANDLE": "বিয়ারিশ ক্যান্ডেল",
    }.get(label or "", label or "-")


def candle_summary_bn(summary):
    return {
        "candle data unavailable": "ক্যান্ডেল ডাটা পাওয়া যায়নি",
        "flat candle / no usable range": "ফ্ল্যাট ক্যান্ডেল / ব্যবহারযোগ্য range নেই",
        "strong green body closing near high": "শক্তিশালী সবুজ বডি, দিনের high-এর কাছে ক্লোজ",
        "strong red body closing near low": "শক্তিশালী লাল বডি, দিনের low-এর কাছে ক্লোজ",
        "lower wick rejection / buyers defended dip": "নিচে wick rejection, dip-এ buyer support দেখা গেছে",
        "upper wick rejection / sellers active near high": "উপরে wick rejection, high-এর কাছে seller active",
        "small body / indecision": "ছোট বডি, বাজারে দ্বিধা",
        "green candle with constructive close": "সবুজ ক্যান্ডেল, গঠনমূলক ক্লোজ",
        "red candle with weak close": "লাল ক্যান্ডেল, দুর্বল ক্লোজ",
    }.get(summary or "", summary or "-")


def explanation_bn(reason):
    reason = str(reason or "")
    if reason.startswith("candle: "):
        return "ক্যান্ডেল: " + candle_summary_bn(reason.split(": ", 1)[1])
    m = re.match(r"RSI ([\d.]+) overbought", reason)
    if m:
        return f"RSI {m.group(1)} overbought zone-এ"
    m = re.match(r"RSI ([\d.]+) bullish momentum", reason)
    if m:
        return f"RSI {m.group(1)} বুলিশ momentum দেখাচ্ছে"
    m = re.match(r"RSI ([\d.]+) oversold bounce risk", reason)
    if m:
        return f"RSI {m.group(1)} oversold bounce-এর সম্ভাবনা দেখাচ্ছে"
    m = re.match(r"RSI ([\d.]+) weak", reason)
    if m:
        return f"RSI {m.group(1)} দুর্বল"
    m = re.match(r"volume ([\d.]+)x average", reason)
    if m:
        return f"volume average-এর {m.group(1)}x"
    m = re.match(r"value traded ([\d.]+)mn", reason)
    if m:
        return f"লেনদেন মূল্য {m.group(1)}mn"
    m = re.match(r"testing resistance ([\d.]+)", reason)
    if m:
        return f"resistance {m.group(1)} পরীক্ষা করছে"
    m = re.match(r"near support ([\d.]+)", reason)
    if m:
        return f"support {m.group(1)}-এর কাছে"
    return {
        "trend UP": "ট্রেন্ড ঊর্ধ্বমুখী",
        "trend DOWN": "ট্রেন্ড নিম্নমুখী",
        "trend SIDE": "ট্রেন্ড সাইডওয়ে",
        "price above SMA20": "দাম SMA20-এর ওপরে",
        "price below SMA20": "দাম SMA20-এর নিচে",
        "price below SMA50": "দাম SMA50-এর নিচে",
        "weak value participation": "লেনদেনে অংশগ্রহণ দুর্বল",
        "upper-circuit chase risk": "upper circuit chase risk আছে",
        "sharp selloff / falling-knife risk": "তীব্র selloff / falling-knife risk",
        "limited stored history": "stored history সীমিত",
    }.get(reason, reason)


def reason_bn(reason):
    reason = str(reason or "")
    m = re.match(r"\+([\d.]+)% on ([\d.]+)mn vol, closing strong", reason)
    if m:
        return f"+{m.group(1)}% মুভ, {m.group(2)}mn value, শক্তিশালী close"
    m = re.match(r"([-\d.]+)% dip on volume", reason)
    if m:
        return f"{m.group(1)}% dip, volume আছে - support confirmation দেখুন"
    m = re.match(r"spike ([\d.]+)%", reason)
    if m:
        return f"{m.group(1)}% spike - overbought/chase risk"
    m = re.match(r"illiquid \(([\d.]+)mn traded\)", reason)
    if m:
        return f"illiquid ({m.group(1)}mn traded) - exit কঠিন হতে পারে"
    m = re.match(r"crash ([-\d.]+)%", reason)
    if m:
        return f"{m.group(1)}% crash - falling knife risk"
    m = re.match(r"stable ([+-][\d.]+)%", reason)
    if m:
        return f"স্থিতিশীল {m.group(1)}%"
    return reason


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
    html = None
    try:
        html = fetch(COMPANY_URL.format(code=code), f"company_{code}", ttl=3600)
        c = parse_company(html, code)
    except Exception:
        c = {}
    out["pe"] = c.get("pe")
    out["category"] = c.get("market_category")
    out["sector"] = c.get("sector")
    out["range_52w"] = c.get("moving_range_52w")
    out["div_yield"] = _div_yield(c, row.get("ltp"))
    out["score"] = None
    out["signal"] = out.get("tag")
    out["technical"] = None
    out["fundamental"] = None
    out["pattern_summary"] = None
    out["prediction"] = None
    out["indicators"] = {}
    out["history"] = []

    fscore = None
    if html:
        try:
            more = fundamentals.parse_more(html, code)
            f = {**c, **more}
            f["pb"] = round(row.get("ltp") / f["nav"], 2) if f.get("nav") and row.get("ltp") else None
            f["div_yield"] = out["div_yield"]
            f["eps_positive"] = bool(f.get("eps_basic") and f.get("eps_basic") > 0)
            hist_eps = f.get("eps_history") or []
            f["eps_growth"] = bool(len(hist_eps) >= 2 and hist_eps[0] > hist_eps[-1])
            fscore, _notes = fundamentals.fundamental_score(f)
            out["fundamental"] = fscore
        except Exception:
            fscore = None

    try:
        h = store.history(code)
        if len(h) >= 30:
            ic = indicators.compute(h)
            pt = patterns.analyze(h, ic)
            comp = score.composite(out, ic, pt, fscore)
            out.update(comp)
            out["pattern_summary"] = pt["summary"]
            out["prediction"] = prediction.predict(out, h, ic, pt)
            out["indicators"] = ic
            out["history"] = h
        else:
            out["prediction"] = prediction.predict(out, [], {}, {})
    except Exception:
        out["prediction"] = prediction.predict(out, [], {}, {})
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

    buy_candidates = [r for r in rated if r["tag"] == "BUY-WATCH" and (r.get("value_mn") or 0) >= 5]
    buy = [enrich(r) for r in buy_candidates]
    buy.sort(key=lambda r: (r.get("score") is not None, r.get("score") or 0, r.get("value_mn") or 0), reverse=True)
    buy = [r for r in buy if r.get("signal") in (None, "BUY", "WATCH", "BUY-WATCH")][:buy_n]
    watch = [r for r in rated if r["tag"] in ("WATCH-DIP", "WAIT") and (r.get("value_mn") or 0) >= 3]
    watch.sort(key=lambda r: r.get("value_mn") or 0, reverse=True)
    watch = [enrich(r) for r in watch[:watch_n]]
    watch.sort(key=lambda r: (r.get("score") is not None, r.get("score") or 0, r.get("value_mn") or 0), reverse=True)
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
        meta = enrich(r) if r else {}
        div_per_share = None
        if meta.get("div_yield") and ltp:
            div_per_share = meta["div_yield"] / 100 * ltp
        positions.append({**h, "ltp": ltp, "cost": cost, "mval": mval, "pnl": pnl,
                          "pnl_pct": (pnl / cost * 100) if pnl is not None and cost else None,
                          "day": _pct_change(r) if r else None,
                          "tag": (meta.get("signal") or _rate(r)[0]) if r else "NO-DATA",
                          "sector": meta.get("sector"), "div_per_share": div_per_share})
    return {"positions": positions, "invested": invested, "market": market,
            "pnl": market - invested, "ret": ((market - invested) / invested * 100) if invested else None}


def portfolio_analytics(port):
    total = port.get("market") or sum(p.get("mval") or 0 for p in port["positions"]) or 1
    weights = sorted(
        ((p["code"], round((p.get("mval") or 0) / total * 100, 1)) for p in port["positions"]),
        key=lambda x: -x[1],
    )
    sectors = {}
    for p in port["positions"]:
        sector = p.get("sector") or "Unknown"
        sectors[sector] = round(sectors.get(sector, 0) + (p.get("mval") or 0) / total * 100, 1)
    income = sum((p.get("quantity") or 0) * (p.get("div_per_share") or 0) for p in port["positions"])
    notes = []
    if weights and weights[0][1] > 40:
        notes.append(f"কনসেন্ট্রেশন ঝুঁকি: {weights[0][0]} মোট পোর্টফোলিওর {weights[0][1]}%")
    big_sector = max(sectors.items(), key=lambda x: x[1], default=(None, 0))
    if big_sector[1] > 50:
        notes.append(f"সেক্টর এক্সপোজার বেশি: {big_sector[0]} {big_sector[1]}%")
    return {
        "weights": weights,
        "sectors": sectors,
        "top_weight": weights[0] if weights else (None, 0),
        "dividend_income": round(income, 2),
        "notes": notes,
    }


# --------------------------------------------------------------------------- #
# PDF primitives
# --------------------------------------------------------------------------- #
class Report(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_y(8)
        doc_font(self, "B", 9)
        self.set_text_color(*NAVY)
        self.cell(0, 5, S("ডিএসই দৈনিক বিশ্লেষণ"))
        doc_font(self, "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 5, datetime.now().strftime("%d %b %Y"), align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*LINE)
        self.line(self.l_margin, 15, self.w - self.r_margin, 15)
        self.ln(6)

    def footer(self):
        self.set_y(-13)
        doc_font(self, "I", 7)
        self.set_text_color(*GREY)
        self.multi_cell(0, 4,
            S("ডাটা dsebd.org থেকে সংগ্রহ করা (delayed/EOD)। এটি rule-based screen, শিক্ষা ও সিদ্ধান্ত সহায়তার জন্য - "
              "ফাইন্যান্সিয়াল অ্যাডভাইস নয়। ট্রেডের আগে official DSE-তে যাচাই করুন।   "
              f"পৃষ্ঠা {self.page_no()}"), align="C")


def section(pdf, title, color=NAVY):
    pdf.ln(2)
    pdf.set_fill_color(*color)
    pdf.set_text_color(*WHITE)
    doc_font(pdf, "B", 11)
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
        doc_font(pdf, "", 7)
        pdf.set_text_color(*GREY)
        pdf.cell(w - 4, 4, S(label.upper()))
        pdf.set_xy(x + 2, y0 + 7.5)
        doc_font(pdf, "B", 12)
        pdf.set_text_color(*color)
        pdf.cell(w - 4, 6, S(value))
    pdf.set_xy(x0, y0 + 16 + 2)


def table(pdf, headers, widths, aligns, rows, zebra=True):
    """rows: list of list-of-cells; a cell is str or (str, rgb_color)."""
    doc_font(pdf, "B", 7.5)
    pdf.set_fill_color(*NAVY)
    pdf.set_text_color(*WHITE)
    pdf.set_draw_color(*LINE)
    for h, w, a in zip(headers, widths, aligns):
        pdf.cell(w, 7, S(h), border=0, align=a, fill=True)
    pdf.ln(7)
    doc_font(pdf, "", 7.5)
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
def ensure_space(pdf, needed=35):
    if pdf.get_y() + needed > pdf.h - pdf.b_margin:
        pdf.add_page()


def _pdf_image(pdf, path, x=None, y=None, w=0, h=0):
    try:
        pdf.image(path, x=x, y=y, w=w, h=h)
        return True
    except Exception:
        return False


def market_charts_section(pdf, data, tmpdir):
    try:
        breadth = charts.breadth_bar(data.get("breadth", {}), os.path.join(tmpdir, "breadth.png"))
        sectors = {}
        for row in data.get("buy", []) + data.get("watch", []):
            sectors[row.get("sector") or "Unknown"] = sectors.get(row.get("sector") or "Unknown", 0) + 1
        sector = charts.sector_pie(sectors or {"No candidates": 1}, os.path.join(tmpdir, "sectors.png"))
    except Exception:
        return
    ensure_space(pdf, 50)
    section(pdf, "মার্কেট ব্রেডথ ও ক্যান্ডিডেট মিক্স", NAVY2)
    y = pdf.get_y()
    if _pdf_image(pdf, breadth, x=pdf.l_margin, y=y, w=68):
        _pdf_image(pdf, sector, x=pdf.l_margin + 84, y=y - 2, w=48)
        pdf.set_y(y + 43)


def cover(pdf, data, port, investor, cash):
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, pdf.w, 30, "F")
    pdf.set_xy(pdf.l_margin, 8)
    doc_font(pdf, "B", 19)
    pdf.set_text_color(*WHITE)
    pdf.cell(0, 9, S("ডিএসই দৈনিক মার্কেট অ্যানালাইসিস"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(pdf.l_margin)
    doc_font(pdf, "", 9)
    pdf.set_text_color(200, 215, 230)
    label = f"Dhaka Stock Exchange   |   {datetime.now().strftime('%A, %d %B %Y  %H:%M')} BDT"
    if investor:
        label += f"   |   Investor: {investor}"
    pdf.cell(0, 6, S(label))
    pdf.ln(20)

    reg = data["regime"]; b = data["breadth"]
    rc = GREEN if reg == "BULLISH" else RED if reg == "BEARISH" else AMBER
    items = [("মার্কেট", reg, rc),
             ("উত্থান / পতন", f"{b['adv']} / {b['dec']}", GREEN if b['adv'] > b['dec'] else RED),
             ("লেনদেন মূল্য (mn)", money(b["value_mn"]), NAVY)]
    if port:
        items += [("পোর্টফোলিও মূল্য", money(port["market"]), NAVY),
                  ("অবাস্তবায়িত P&L", money(port["pnl"]), pnl_color(port["pnl"])),
                  ("রিটার্ন", f"{num(port['ret'],2)}%", pnl_color(port["pnl"]))]
        if cash:
            items.append(("মোট ইকুইটি", money(port["market"] + cash), NAVY))
    # split into rows of up to 4
    for i in range(0, len(items), 4):
        kpi_band(pdf, items[i:i + 4])


def executive_summary(pdf, data, port):
    section(pdf, "নির্বাহী সারাংশ", NAVY2)
    b = data["breadth"]
    buy = data.get("buy") or []
    watch = data.get("watch") or []
    avoid = data.get("avoid") or []
    top = buy[0] if buy else None
    pred = top.get("prediction") if top else None
    lines = [
        f"মার্কেট অবস্থা: {data['regime']} | উত্থান {b['adv']} / পতন {b['dec']} | মোট লেনদেন {money(b['value_mn'])} mn।",
        f"আজকের পরিষ্কার BUY-WATCH প্রার্থী: {len(buy)}টি | অপেক্ষার তালিকা: {len(watch)}টি | ঝুঁকি/এড়িয়ে চলার তালিকা: {len(avoid)}টি।",
    ]
    if top:
        line = f"প্রধান প্রার্থী: {top['code']} | LTP {num(top.get('ltp'))} | পরিবর্তন {(top.get('pct') or 0):+.1f}% | স্কোর {top.get('score') or '-'}।"
        if pred:
            line += f" পূর্বাভাস: {pred_bn(pred.get('label'))} ({pred.get('probability_pct')}%, {pred.get('confidence')} confidence)।"
        lines.append(line)
    else:
        lines.append("আজ পরিষ্কার BUY-WATCH সেটআপ নেই; ধৈর্য ধরে ভালো এন্ট্রির অপেক্ষা করা ভালো।")
    if port:
        lines.append(f"আপনার পোর্টফোলিও: বাজার মূল্য Tk {money(port['market'])} | P&L Tk {money(port['pnl'])} ({num(port['ret'], 2)}%)।")
    lines.append("সব সিদ্ধান্তে liquidity, news catalyst, support/resistance এবং official DSE data যাচাই করা জরুরি।")
    doc_font(pdf, "", 9)
    pdf.set_text_color(35, 40, 45)
    for line in lines:
        pdf.multi_cell(0, 5.5, S("- " + line), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def portfolio_section(pdf, port, cash, tmpdir=None):
    section(pdf, "আপনার পোর্টফোলিও - লাইভ লাভ/লোকসান", NAVY2)
    headers = ["কোড", "পরিমাণ", "এভারেজ", "LTP", "খরচ", "মার্কেট ভ্যালু", "P&L", "P&L%", "Day%", "সিগন্যাল"]
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
    doc_font(pdf, "B", 8)
    pdf.set_text_color(*NAVY)
    pdf.cell(sum(widths[:4]), 7, "TOTAL", align="L")
    pdf.cell(widths[4], 7, money(port["invested"]), align="R")
    pdf.cell(widths[5], 7, money(port["market"]), align="R")
    pdf.set_text_color(*pnl_color(port["pnl"]))
    pdf.cell(widths[6], 7, money(port["pnl"]), align="R")
    pdf.cell(widths[7], 7, num(port["ret"], 2), align="R")
    pdf.ln(9)
    doc_font(pdf, "", 8)
    pdf.set_text_color(*GREY)
    line = (f"মোট খরচ Tk {money(port['invested'])}   বাজার মূল্য Tk {money(port['market'])}   "
            f"অবাস্তবায়িত P&L Tk {money(port['pnl'])} ({num(port['ret'],2)}%)")
    if cash:
        line += f"   ক্যাশ Tk {money(cash)}   মোট ইকুইটি Tk {money(port['market'] + cash)}"
    pdf.multi_cell(0, 5, S(line), new_x="LMARGIN", new_y="NEXT")
    # quick read on positions
    worst = min(port["positions"], key=lambda p: p.get("pnl_pct") or 0, default=None)
    if worst and (worst.get("pnl_pct") or 0) < -5:
        pdf.set_text_color(*RED)
        pdf.multi_cell(0, 5, S(f"সবচেয়ে দুর্বল পজিশন: {worst['code']} {num(worst['pnl_pct'],1)}% - average down করার আগে thesis আবার যাচাই করুন।"),
                       new_x="LMARGIN", new_y="NEXT")
    analytics = portfolio_analytics(port)
    if tmpdir:
        try:
            alloc = charts.portfolio_alloc(port["positions"], os.path.join(tmpdir, "portfolio.png"))
            ensure_space(pdf, 58)
            y = pdf.get_y() + 3
            _pdf_image(pdf, alloc, x=pdf.l_margin, y=y, w=52)
            pdf.set_xy(pdf.l_margin + 62, y + 2)
            doc_font(pdf, "B", 8)
            pdf.set_text_color(*NAVY)
            pdf.cell(0, 5, S("পোর্টফোলিও অ্যানালিটিক্স"), new_x="LMARGIN", new_y="NEXT")
            doc_font(pdf, "", 8)
            pdf.set_text_color(40, 45, 50)
            lines = [
                f"সবচেয়ে বড় ওজন: {analytics['top_weight'][0] or '-'} {analytics['top_weight'][1]}%",
                f"আনুমানিক ডিভিডেন্ড আয়: Tk {money(analytics['dividend_income'])}",
            ] + analytics["notes"]
            for line in lines:
                pdf.set_x(pdf.l_margin + 62)
                pdf.multi_cell(0, 5, S(line), new_x="LMARGIN", new_y="NEXT")
            pdf.set_y(max(pdf.get_y(), y + 50))
        except Exception:
            pass


def candidate_block(pdf, i, r, kind, tmpdir=None):
    lv = r.get("levels") or _levels(r)
    pct = r.get("pct") or 0
    doc_font(pdf, "B", 10)
    pdf.set_text_color(*NAVY)
    pdf.cell(70, 6, S(f"{i}. {r['code']}"))
    doc_font(pdf, "B", 9)
    pdf.set_text_color(*pnl_color(pct))
    pdf.cell(0, 6, f"{pct:+.1f}%   LTP {num(r.get('ltp'))}", align="R", new_x="LMARGIN", new_y="NEXT")
    flags = []
    if r.get("pe") is not None and r["pe"] > 40:
        flags.append("HIGH P/E")
    if (r.get("category") or "").upper() in ("B", "N", "Z"):
        flags.append(f"Cat {r['category']}")
    if (r.get("div_yield") or 0) == 0:
        flags.append("no div")
    doc_font(pdf, "", 8)
    pdf.set_text_color(*GREY)
    meta = (f"P/E {num(r.get('pe'),1)}   Div~{num(r.get('div_yield'),1)}%   Cat {r.get('category') or '-'}   "
            f"Vol {num(r.get('value_mn'),1)}mn   {r.get('sector') or ''}")
    if flags:
        meta += "    [!] " + ", ".join(flags)
    pdf.multi_cell(0, 4.6, S(meta), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(40, 45, 50)
    pdf.multi_cell(0, 4.6, S(f"কারণ: {reason_bn(r.get('reason',''))}"), new_x="LMARGIN", new_y="NEXT")
    if r.get("score") is not None:
        sig_color = GREEN if r.get("signal") == "BUY" else AMBER if r.get("signal") == "WATCH" else GREY
        doc_font(pdf, "B", 8)
        pdf.set_text_color(*sig_color)
        fund = r.get("fundamental") if r.get("fundamental") is not None else "-"
        pdf.multi_cell(
            0,
            4.6,
            S(f"স্কোর {r.get('score')}/100   টেকনিক্যাল {r.get('technical')}   ফান্ডামেন্টাল {fund}   {signal_bn(r.get('signal'))}"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
    if tmpdir and r.get("history"):
        try:
            png = charts.price_chart(r["history"], r.get("indicators") or {}, os.path.join(tmpdir, f"{r['code']}_{i}.png"))
            ensure_space(pdf, 45)
            _pdf_image(pdf, png, w=95)
            pdf.ln(1)
        except Exception:
            pass
    if r.get("pattern_summary"):
        doc_font(pdf, "", 8)
        pdf.set_text_color(40, 45, 50)
        pdf.multi_cell(0, 4.6, S(f"প্যাটার্ন: {r['pattern_summary']}"), new_x="LMARGIN", new_y="NEXT")
    if r.get("prediction"):
        pred = r["prediction"]
        candle = pred.get("candle") or {}
        doc_font(pdf, "B", 8)
        pdf.set_text_color(*AMBER)
        pdf.multi_cell(
            0,
            4.6,
            S(
                f"পূর্বাভাস: {pred_bn(pred.get('label'))} ({pred.get('probability_pct')}%, "
                f"confidence {confidence_bn(pred.get('confidence'))}, {horizon_bn(pred.get('horizon'))})"
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        doc_font(pdf, "", 8)
        pdf.set_text_color(40, 45, 50)
        pdf.multi_cell(
            0,
            4.6,
            S(
                f"ক্যান্ডেল: {candle_summary_bn(candle.get('summary'))} | "
                f"ব্যাখ্যা: {'; '.join(explanation_bn(x) for x in pred.get('explanation', [])[:4])}"
            ),
            new_x="LMARGIN",
            new_y="NEXT",
        )
    pdf.set_text_color(*NAVY)
    if kind == "buy":
        plan = (f"পরিকল্পনা: dip entry {num(lv['support'])} অথবা {num(lv['resistance'])} এর ওপরে breakout।  "
                f"Stop {num(lv['stop'])}.  Target {num(lv['target'])} (52w high).  52w {r.get('range_52w') or '-'}.")
    else:
        plan = (f"পর্যবেক্ষণ: {num(lv['support'])} pullback অথবা volume সহ {num(lv['resistance'])} এর ওপরে confirmation।  "
                f"52w {r.get('range_52w') or '-'}.")
    pdf.multi_cell(0, 4.6, S(plan), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*LINE)
    pdf.line(pdf.l_margin, pdf.get_y() + 1.5, pdf.w - pdf.r_margin, pdf.get_y() + 1.5)
    pdf.ln(3.5)


def avoid_section(pdf, avoid):
    section(pdf, "এড়িয়ে চলুন / ঝুঁকি", RED)
    headers = ["কোড", "পরিবর্তন", "কারণ"]
    widths = [34, 24, 132]
    rows = []
    for r in avoid:
        chg = "no trade" if (r.get("value_mn") or 0) < 0.5 else f"{(r.get('pct') or 0):+.1f}%"
        rows.append([r["code"], (chg, pnl_color(r.get("pct"))), reason_bn(r.get("reason", ""))])
    table(pdf, headers, widths, ["L", "R", "L"], rows)


def prediction_section(pdf, data):
    picks = [r for r in data.get("buy", []) + data.get("watch", []) if r.get("prediction")]
    if not picks:
        return
    ensure_space(pdf, 70)
    section(pdf, "পূর্বাভাস / সিনারিও রিড - ক্যান্ডেল আচরণ + ইন্ডিকেটর", AMBER)
    doc_font(pdf, "", 8.5)
    pdf.set_text_color(40, 45, 50)
    pdf.multi_cell(
        0,
        5,
        S(
            "পরবর্তী ১-৫ সেশনের সম্ভাব্য সিনারিও। এটি নিয়মভিত্তিক সম্ভাবনা বিশ্লেষণ, "
            "নিশ্চিত ভবিষ্যদ্বাণী নয়। DSE live scrape-এ দিনের প্রকৃত open না থাকলে "
            "ক্যান্ডেল আচরণ হিসাব করতে YCP আনুমানিক open হিসেবে ব্যবহার করা হয়।"
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(1)

    usable_w = pdf.w - pdf.l_margin - pdf.r_margin
    for r in picks[:8]:
        ensure_space(pdf, 25)
        pred = r["prediction"]
        candle = pred.get("candle") or {}
        label = pred.get("label")
        col = GREEN if "BULLISH" in label else RED if ("BEARISH" in label or "RISK" in label) else AMBER

        pdf.set_fill_color(*LIGHT)
        pdf.set_draw_color(*LINE)
        y = pdf.get_y()
        pdf.rect(pdf.l_margin, y, usable_w, 9, "DF")
        pdf.set_xy(pdf.l_margin + 2, y + 1.7)
        doc_font(pdf, "B", 8.5)
        pdf.set_text_color(*NAVY)
        pdf.cell(28, 5, S(r["code"]))
        pdf.set_text_color(*col)
        pdf.cell(54, 5, S(pred_bn(label)))
        pdf.set_text_color(35, 40, 45)
        pdf.cell(26, 5, S(f"Prob {pred.get('probability_pct')}%"))
        pdf.cell(34, 5, S(f"Conf {confidence_bn(pred.get('confidence'))}"))
        pdf.cell(0, 5, S(candle_label_bn(candle.get("label"))), new_x="LMARGIN", new_y="NEXT")

        doc_font(pdf, "", 8)
        pdf.set_text_color(40, 45, 50)
        pdf.multi_cell(
            0,
            4.8,
            S(f"ক্যান্ডেল: {candle_summary_bn(candle.get('summary'))}"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        reasons = "； ".join(explanation_bn(x) for x in pred.get("explanation", [])[:5])
        pdf.multi_cell(
            0,
            4.8,
            S(f"ব্যাখ্যা: {reasons}"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.ln(1.5)

    pdf.ln(2)
    doc_font(pdf, "I", 8)
    pdf.set_text_color(*GREY)
    pdf.multi_cell(
        0,
        4.8,
        S("এই পূর্বাভাস অংশটি শুধু শিক্ষা ও সিদ্ধান্ত সহায়তার জন্য। ট্রেডের আগে news, fundamentals, liquidity এবং official DSE data যাচাই করুন।"),
        new_x="LMARGIN",
        new_y="NEXT",
    )


def ai_prediction_section(pdf, text):
    if not text:
        return
    ensure_space(pdf, 60)
    section(pdf, "AI Prediction - Claude/Codex ব্যাখ্যা", AMBER)
    doc_font(pdf, "", 8.8)
    pdf.set_text_color(35, 40, 45)
    clean = str(text).strip()
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    for block in clean.splitlines():
        line = block.strip()
        if not line:
            pdf.ln(1.5)
            continue
        if len(line) <= 38 and (line.endswith(":") or line.lower() == "ai prediction"):
            ensure_space(pdf, 12)
            doc_font(pdf, "B", 9)
            pdf.set_text_color(*NAVY)
            pdf.multi_cell(0, 5.2, S(line), new_x="LMARGIN", new_y="NEXT")
            doc_font(pdf, "", 8.8)
            pdf.set_text_color(35, 40, 45)
            continue
        ensure_space(pdf, 14)
        pdf.multi_cell(0, 5.2, S(line), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def methodology(pdf):
    ensure_space(pdf, 90)
    section(pdf, "শেয়ার কীভাবে বাছাই করা হয় (মেথডোলজি)", NAVY2)
    doc_font(pdf, "", 9)
    pdf.set_text_color(40, 45, 50)
    intro = ("প্রতিটি ট্রেড হওয়া শেয়ারকে দিনের price action, volume, liquidity, trend, RSI/SMA, "
             "support/resistance এবং available fundamentals দিয়ে rule-based ভাবে স্কোর করা হয়। "
             "এটি decision-support screen, নিশ্চিত buy/sell নির্দেশ নয়।")
    pdf.multi_cell(0, 5, S(intro), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    items = [
        ("BUY-WATCH", GREEN, "বাস্তব volume-সহ শক্তিশালী মুভ, কিন্তু upper circuit chase নয়। Entry zone, stop ও target দেখে সিদ্ধান্ত নিতে হবে।"),
        ("WATCH-DIP", (40, 90, 160), "ভলিউমসহ pullback/support test। Base, reversal candle অথবা breakout confirmation ছাড়া তাড়া করা ঠিক নয়।"),
        ("WAIT", AMBER, "দিনের মুভ খুব বেশি বা overbought। আজ chase না করে pullback/confirmation অপেক্ষা করা ভালো।"),
        ("AVOID", RED, "বড় পতন, falling-knife setup, অথবা liquidity খুব কম। Exit কঠিন হতে পারে।"),
        ("HOLD / NEUTRAL", GREY, "মুভ ছোট, conviction কম, অথবা পরিষ্কার edge নেই।"),
    ]
    for tag, col, desc in items:
        doc_font(pdf, "B", 9); pdf.set_text_color(*col)
        pdf.cell(34, 5.5, S(tag))
        doc_font(pdf, "", 9); pdf.set_text_color(40, 45, 50)
        pdf.multi_cell(0, 5.5, S(desc), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(0.5)
    pdf.ln(2)
    section(pdf, "ক্যান্ডিডেটদের ঝুঁকি ফ্ল্যাগ", NAVY2)
    doc_font(pdf, "", 9); pdf.set_text_color(40, 45, 50)
    for f in [
        "HIGH P/E - valuation expensive/speculative হতে পারে।",
        "Cat B / N / Z - DSE category দুর্বল; Z হলে dividend/operations নিয়ে extra caution।",
        "no div - সাম্প্রতিক cash dividend নেই।",
        "Entry / Stop / Target - support কাছে dip-entry, stop support-এর নিচে, target resistance/52-week high ভিত্তিক।",
        "Prediction - candle behavior, trend, RSI, SMA, volume ও support/resistance থেকে next 1-5 session scenario; guarantee নয়।",
        "Candle behavior - live DSE scrape-এ true open না থাকলে YCP approximate session-open proxy হিসেবে ব্যবহৃত হয়।",
    ]:
        pdf.multi_cell(0, 5.5, S("- " + f), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    doc_font(pdf, "B", 9); pdf.set_text_color(*RED)
    pdf.multi_cell(0, 5,
        S("এটি research ও decision-support এর জন্য rule-based technical screen - financial advice নয়। "
          "BD market-এ low liquidity ও manipulation risk থাকতে পারে; ট্রেডের আগে fundamentals, news এবং official DSE data যাচাই করুন।"),
        new_x="LMARGIN", new_y="NEXT")


def backtest_section(pdf):
    path = os.path.join(REPORTS_DIR, "backtest.json")
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return
    ensure_space(pdf, 55)
    section(pdf, "ব্যাকটেস্ট যাচাই", NAVY2)
    doc_font(pdf, "", 9)
    pdf.set_text_color(40, 45, 50)
    pdf.multi_cell(
        0,
        5,
        S(
            f"সংরক্ষিত historical data দিয়ে walk-forward validation। Horizon: {data.get('horizon', '-')}"
            " trading days। অতীত signal behavior একটি measurement, নিশ্চিত prediction নয়।"
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    rows = []
    for sig, val in sorted((data.get("by_signal") or {}).items()):
        rows.append([sig, val.get("n", 0), f"{val.get('win_rate', 0)}%", f"{val.get('avg_ret', 0)}%"])
    if rows:
        table(pdf, ["সিগন্যাল", "N", "Win Rate", "Avg Return"], [45, 30, 45, 45], ["L", "R", "R", "R"], rows)


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
def build_pdf(data, port, when, investor=None, cash=0.0, ai_text=None):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    tmpdir = tempfile.mkdtemp(prefix="dse_report_")
    pdf = Report()
    setup_fonts(pdf)
    if hasattr(pdf, "set_text_shaping"):
        try:
            pdf.set_text_shaping(True)
        except Exception:
            pass
    pdf.set_auto_page_break(auto=True, margin=16)
    try:
        pdf.add_page()
        cover(pdf, data, port, investor, cash)
        executive_summary(pdf, data, port)
        market_charts_section(pdf, data, tmpdir)
        prediction_section(pdf, data)
        ai_prediction_section(pdf, ai_text)

        if port and port["positions"]:
            portfolio_section(pdf, port, cash, tmpdir)

        section(pdf, "BUY-WATCH প্রার্থী - স্কোর, প্যাটার্ন ও পূর্বাভাস", GREEN)
        if data["buy"]:
            for i, r in enumerate(data["buy"], 1):
                candidate_block(pdf, i, r, "buy", tmpdir)
        else:
            doc_font(pdf, "I", 9); pdf.set_text_color(*GREY)
            pdf.multi_cell(0, 6, S("আজ পরিষ্কার buy setup নেই। ধৈর্য ধরুন; forced trade এড়ানোই ভালো।"), new_x="LMARGIN", new_y="NEXT")

        section(pdf, "ওয়াচলিস্ট - সঠিক এন্ট্রির অপেক্ষা", NAVY)
        if data["watch"]:
            for i, r in enumerate(data["watch"], 1):
                candidate_block(pdf, i, r, "watch", tmpdir)
        else:
            doc_font(pdf, "I", 9); pdf.set_text_color(*GREY)
            pdf.multi_cell(0, 6, S("আজ ওয়াচলিস্টে পরিষ্কার setup নেই।"), new_x="LMARGIN", new_y="NEXT")

        avoid_section(pdf, data["avoid"])
        backtest_section(pdf)
        methodology(pdf)

        fname = f"DSE_Analysis_{when.strftime('%Y-%m-%d_%H%M')}_BDT.pdf"
        path = os.path.join(REPORTS_DIR, fname)
        pdf.output(path)
        return path
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    p = argparse.ArgumentParser(description="Generate dated DSE analysis PDF")
    p.add_argument("--buy", type=int, default=6)
    p.add_argument("--watch", type=int, default=6)
    p.add_argument("--portfolio", default=os.path.join("data", "portfolio.csv"))
    p.add_argument("--cash", type=float, default=0.0, help="ledger/cash balance for total equity")
    p.add_argument("--investor", default=None, help="investor code shown on the cover")
    p.add_argument("--ai-commentary-file", default=None, help="optional Claude/Codex-written Bangla commentary file to embed in the PDF")
    p.add_argument("--ai-commentary-stdin", action="store_true", help="read optional Claude/Codex commentary from stdin")
    args = p.parse_args()

    when = datetime.now()
    data = select(args.buy, args.watch)
    port = load_portfolio(args.portfolio)
    ai_text = None
    if args.ai_commentary_file:
        with open(args.ai_commentary_file, encoding="utf-8") as f:
            ai_text = f.read().strip()
    elif args.ai_commentary_stdin:
        ai_text = sys.stdin.read().strip()
    path = build_pdf(data, port, when, investor=args.investor, cash=args.cash, ai_text=ai_text)
    print(path)


if __name__ == "__main__":
    main()
