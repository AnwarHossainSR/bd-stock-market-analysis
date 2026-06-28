"""Deeper company fundamentals and a transparent 0-100 fundamental score."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

import dse


def parse_more(html, code):
    soup = BeautifulSoup(html, "html.parser")
    cells = [c.get_text(" ", strip=True) for c in soup.find_all(["td", "th"])]

    def after(label):
        llabel = label.lower()
        for i, cell in enumerate(cells):
            c = cell.strip()
            lc = c.lower()
            if lc == llabel:
                if i + 1 < len(cells):
                    return cells[i + 1]
            if lc.startswith(llabel + " "):
                tail = c[len(label):].strip(" :")
                if tail:
                    return tail
                if i + 1 < len(cells):
                    return cells[i + 1]
        return None

    text = soup.get_text(" ", strip=True)
    eps_src = after("EPS") or after("Basic") or ""
    eps_hist = [float(x) for x in re.findall(r"-?\d+\.\d+", eps_src)][:8]
    div = after("Dividend History") or after("Dividend") or ""
    if not re.search(r"\d{4}", div):
        md = re.search(r"((?:\d+(?:\.\d+)?%\s*\d{4}\s*,?\s*){1,})", text)
        div = md.group(1) if md else ""
    return {
        "nav": dse._num(after("NAV per Share") or after("NAV")),
        "reserve_surplus_mn": dse._num(after("Reserve") or after("Reserve & Surplus")),
        "eps_history": eps_hist,
        "dividend_years": len(set(re.findall(r"\d{4}", div))),
    }


def enrich_fundamentals(code, ltp):
    html = dse.fetch(dse.COMPANY_URL.format(code=code), f"company_{code}", ttl=3600)
    base = dse.parse_company(html, code)
    more = parse_more(html, code)
    f = {**base, **more}
    f["pb"] = round(ltp / f["nav"], 2) if f.get("nav") and ltp else None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", f.get("dividend_history") or "")
    f["div_yield"] = (
        round(float(m.group(1)) / 100 * f["face_value"] / ltp * 100, 2)
        if (m and f.get("face_value") and ltp)
        else None
    )
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
            s -= 20
            notes.append("negative/zero P/E")
        elif pe < 10:
            s += 15
            notes.append("low P/E")
        elif pe < 20:
            s += 8
        elif pe > 40:
            s -= 15
            notes.append("very high P/E")
    pb = f.get("pb")
    if pb is not None:
        if pb < 1.5:
            s += 8
            notes.append("below 1.5x book")
        elif pb > 5:
            s -= 8
            notes.append("rich vs book")
    dy = f.get("div_yield") or 0
    if dy >= 5:
        s += 10
        notes.append(f"div yield {dy}%")
    elif dy == 0:
        s -= 8
        notes.append("no dividend")
    if (f.get("dividend_years") or 0) >= 5:
        s += 8
        notes.append("consistent payer")
    if f.get("eps_positive"):
        s += 5
    else:
        s -= 10
        notes.append("EPS not positive")
    if f.get("eps_growth"):
        s += 4
        notes.append("EPS growth")
    cat = (f.get("market_category") or "").upper()
    if cat == "A":
        s += 8
    elif cat in ("B", "N"):
        s -= 5
        notes.append(f"Cat {cat}")
    elif cat == "Z":
        s -= 25
        notes.append("Cat Z - serious concern")
    return max(0, min(100, int(round(s)))), notes
