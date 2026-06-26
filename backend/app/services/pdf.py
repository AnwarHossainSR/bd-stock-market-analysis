"""PDF report generator. Renders a screen() result to a dated, professional PDF."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from app.config import settings
from app.services.screen import _levels

REPORTS_DIR = settings.reports_dir

NAVY = (15, 40, 75)
GREEN = (20, 120, 50)
RED = (165, 30, 30)
GREY = (90, 90, 90)

_UNI = {"—": "-", "–": "-", "‘": "'", "’": "'", "“": '"', "”": '"', "…": "...", "\xa0": " "}


def S(s) -> str:
    """Make text safe for the latin-1 core PDF font."""
    if s is None:
        return ""
    s = str(s)
    for k, v in _UNI.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def _fmt(v, dash="-"):
    return dash if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v))


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


def candidate_block(pdf: Report, i: int, r: dict, kind: str):
    lv = r.get("levels") or _levels(r)
    pct = r.get("pct") or r.get("pct_change") or 0
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 7, f"{i}. {r['code']}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*(GREEN if pct >= 0 else RED))
    pdf.cell(40, 5, f"LTP {_fmt(r.get('ltp'))}  ({pct:+.1f}%)")
    flags = []
    if r.get("pe") is not None and r["pe"] > 40:
        flags.append("HIGH P/E")
    if (r.get("category") or "").upper() in ("B", "N", "Z"):
        flags.append(f"Cat {r['category']} risk")
    if (r.get("div_yield") or 0) == 0:
        flags.append("no div")
    flag_txt = ("   [!] " + ", ".join(flags)) if flags else ""
    pdf.set_text_color(*GREY)
    meta = (f"P/E {_fmt(r.get('pe'))}   Div~{_fmt(r.get('div_yield'))}%   "
            f"Cat {r.get('category') or '-'}   Vol {_fmt(r.get('value_mn'))}mn   "
            f"{r.get('sector') or ''}{flag_txt}")
    pdf.multi_cell(0, 5, S(meta), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 5, S(f"Why: {r.get('reason','')}"), new_x="LMARGIN", new_y="NEXT")
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


def build_pdf(data: dict, when: datetime) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pdf = Report()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 12, "DSE Daily Market Analysis", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 6, f"Dhaka Stock Exchange  |  {when.strftime('%A, %d %B %Y  %H:%M')} BDT",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

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

    section_title(pdf, "BUY CANDIDATES", GREEN)
    if data["buy"]:
        for i, r in enumerate(data["buy"], 1):
            candidate_block(pdf, i, r, "buy")
    else:
        pdf.set_font("Helvetica", "I", 10); pdf.set_text_color(*GREY)
        pdf.multi_cell(0, 6, "No clean buy setups today. Stay patient.", new_x="LMARGIN", new_y="NEXT")

    section_title(pdf, "WATCHLIST", NAVY)
    if data["watch"]:
        for i, r in enumerate(data["watch"], 1):
            candidate_block(pdf, i, r, "watch")
    else:
        pdf.set_font("Helvetica", "I", 10); pdf.set_text_color(*GREY)
        pdf.multi_cell(0, 6, "Nothing on watch today.", new_x="LMARGIN", new_y="NEXT")

    section_title(pdf, "AVOID / RISK", RED)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(0, 0, 0)
    if data["avoid"]:
        for r in data["avoid"]:
            chg = "no trade" if (r.get("value_mn") or 0) < 0.5 else f"{(r.get('pct') or 0):+.1f}%"
            pdf.multi_cell(0, 5, S(f"- {r['code']}  ({chg})  -  {r.get('reason','')}"),
                           new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 5, "None flagged.", new_x="LMARGIN", new_y="NEXT")

    fname = f"DSE_Analysis_{when.strftime('%Y-%m-%d_%H%M')}_BDT.pdf"
    path = REPORTS_DIR / fname
    pdf.output(str(path))
    return path
