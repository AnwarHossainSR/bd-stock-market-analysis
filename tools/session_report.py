"""Compact live-session report writer for DSE action sheets."""
from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

import session

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def _clean_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value)


def _item_line(item: dict) -> str:
    bits = [str(item.get("code", "N/A"))]
    if item.get("ltp") is not None:
        bits.append(f"LTP {item['ltp']}")
    if item.get("pct_change") is not None:
        bits.append(f"{item['pct_change']:+.2f}%")
    if item.get("value_mn") is not None:
        bits.append(f"value {item['value_mn']}mn")
    if item.get("volume_ratio") is not None:
        bits.append(f"vol {item['volume_ratio']}x")
    if item.get("label"):
        bits.append(item["label"])
    return " | ".join(bits)


def render_markdown(sheet: dict) -> str:
    market = sheet["market"]
    health = sheet["data_health"]
    lines = [
        "# DSE Live Session Brief",
        "",
        f"Generated: {sheet['generated_at']}",
        f"Market state: **{sheet['market_state']}**",
        f"Data health: **{health['status']}** - rows {health['rows']}; warnings: {', '.join(health['warnings']) or 'none'}",
        f"Market: **{market['regime']}** - adv {market['advances']}, dec {market['declines']}, unchanged {market['unchanged']}, value {market['total_value_mn']}mn",
        "",
        "## Portfolio Action",
    ]
    portfolio = sheet.get("portfolio")
    if portfolio and portfolio.get("positions"):
        lines.append("| Code | Signal | Score | Trend | P&L | Stop | Target |")
        lines.append("|---|---:|---:|---|---:|---:|---:|")
        for p in portfolio["positions"]:
            lines.append(
                f"| {p['code']} | {p['signal']} | {p.get('score') or 'n/a'} | {p.get('trend') or 'n/a'} | "
                f"{p.get('pnl_pct') if p.get('pnl_pct') is not None else 'n/a'} | "
                f"{p.get('atr_trailing_stop') if p.get('atr_trailing_stop') is not None else 'n/a'} | "
                f"{p.get('resistance') if p.get('resistance') is not None else 'n/a'} |"
            )
    else:
        lines.append("No portfolio positions loaded.")

    sections = [
        ("Top 5 Buy-Watch", sheet.get("buy_watch", [])[:5]),
        ("Top 5 Sell/Reduce Alerts", sheet.get("portfolio_danger_names", [])[:5]),
        ("Avoid / Chase Warnings", sheet.get("avoid_chase_warnings", [])[:5]),
        ("Unusual Volume", sheet.get("unusual_volume", [])[:5]),
    ]
    for title, items in sections:
        lines.extend(["", f"## {title}"])
        if items:
            lines.extend(f"- {_item_line(item)}" for item in items)
        else:
            lines.append("- None.")

    lines.extend(["", sheet["disclaimer"], ""])
    return "\n".join(lines)


def write_markdown(sheet: dict, out_dir: str | Path = REPORTS) -> Path:
    path = Path(out_dir)
    path.mkdir(parents=True, exist_ok=True)
    stamp = _clean_filename(datetime.now().strftime("%Y-%m-%d_%H%M"))
    out = path / f"DSE_Session_{stamp}.md"
    out.write_text(render_markdown(sheet), encoding="utf-8")
    return out


def write_pdf(sheet: dict, out_dir: str | Path = REPORTS) -> Path:
    path = Path(out_dir)
    path.mkdir(parents=True, exist_ok=True)
    stamp = _clean_filename(datetime.now().strftime("%Y-%m-%d_%H%M"))
    out = path / f"DSE_Session_{stamp}.pdf"
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, "DSE Live Session Brief", ln=True)
    pdf.set_font("Helvetica", "", 9)
    for line in render_markdown(sheet).replace("**", "").splitlines()[2:]:
        if line.startswith("#"):
            pdf.set_font("Helvetica", "B", 11)
            pdf.ln(2)
            pdf.multi_cell(0, 6, line.lstrip("# ").strip())
            pdf.set_font("Helvetica", "", 9)
        elif line.startswith("|"):
            pdf.multi_cell(0, 5, line.replace("|", "  ").strip())
        else:
            pdf.multi_cell(0, 5, line)
    pdf.output(str(out))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a compact DSE live-session report")
    parser.add_argument("--pdf", action="store_true", help="write PDF instead of Markdown")
    parser.add_argument("--portfolio", default=str(session.DEFAULT_PORTFOLIO))
    args = parser.parse_args()

    sheet = session.get_action_sheet(portfolio_path=args.portfolio)
    out = write_pdf(sheet) if args.pdf else write_markdown(sheet)
    print(out)


if __name__ == "__main__":
    main()
