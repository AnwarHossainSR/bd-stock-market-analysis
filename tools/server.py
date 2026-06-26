#!/usr/bin/env python3
"""Zero-dependency JSON API + static server for the DSE dashboard.

Wraps the dse.py scraper and report.py PDF generator behind a small HTTP API the
React dashboard (webapp/index.html) consumes. Uses only the Python stdlib.

Run from project root:
    .venv/Scripts/python tools/server.py            # -> http://localhost:8787
    .venv/Scripts/python tools/server.py --port 9000 --no-open

Endpoints
    GET  /api/health
    GET  /api/overview?buy=6&watch=6     screen + breadth + enriched buy/watch/avoid
    GET  /api/prices                     full market table (every share, tagged)
    GET  /api/company?code=GP            fundamentals + trade levels
    GET  /api/portfolio                  holdings P&L
    POST /api/portfolio                  save holdings {holdings:[{code,quantity,buy_price}]}
    GET  /api/report?buy=6&watch=6       build PDF -> {url}
    GET  /reports/<file>.pdf             download a report
    GET  /                               the dashboard

Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import dse
import report

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBAPP = os.path.join(ROOT, "webapp")
REPORTS = os.path.join(ROOT, "reports")
PORTFOLIO_CSV = os.path.join(ROOT, "data", "portfolio.csv")


# --------------------------------------------------------------------------- #
# Data helpers (reuse dse.py / report.py)
# --------------------------------------------------------------------------- #
def overview(buy: int, watch: int) -> dict:
    return report.select(buy, watch)


def prices_table() -> dict:
    rows = dse.get_prices()
    out = []
    for r in rows:
        tag, reason = dse._rate(r)
        out.append({**r, "pct_change": dse._pct_change(r), "tag": tag, "reason": reason})
    return {"fetched_at": dse._now(), "count": len(out), "prices": out}


def company(code: str) -> dict:
    code = code.upper()
    html = dse.fetch(dse.COMPANY_URL.format(code=code), f"company_{code}", ttl=3600)
    c = dse.parse_company(html, code)
    # add live trade levels from the price list
    by = {r["code"].upper(): r for r in dse.get_prices()}
    r = by.get(code, {})
    merged = {**c, **{k: r.get(k) for k in ("ltp", "high", "low", "ycp", "volume", "value_mn")}}
    merged["pct_change"] = dse._pct_change(r) if r else None
    merged["div_yield"] = report._div_yield(c, r.get("ltp") if r else None)
    merged["levels"] = report._levels({**r, "range_52w": c.get("moving_range_52w")})
    return {"company": merged}


def portfolio() -> dict:
    ns = argparse.Namespace(csv=PORTFOLIO_CSV)
    return dse.cmd_portfolio(ns)


def save_portfolio(holdings: list[dict]) -> dict:
    os.makedirs(os.path.dirname(PORTFOLIO_CSV), exist_ok=True)
    with open(PORTFOLIO_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["code", "quantity", "buy_price"])
        for h in holdings:
            if not h.get("code"):
                continue
            w.writerow([str(h["code"]).strip().upper(), h["quantity"], h["buy_price"]])
    return portfolio()


def build_report(buy: int, watch: int) -> dict:
    when = datetime.now()
    data = report.select(buy, watch)
    path = report.build_pdf(data, when)
    return {"url": "/reports/" + os.path.basename(path), "file": os.path.basename(path)}


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #
class Handler(BaseHTTPRequestHandler):
    server_version = "DSE-Dashboard/1.0"

    def log_message(self, *a):  # quieter console
        pass

    # -- helpers --
    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _err(self, msg, code=500):
        self._json({"error": str(msg)}, code)

    def _file(self, path, ctype):
        try:
            with open(path, "rb") as f:
                self._send(200, f.read(), ctype)
        except FileNotFoundError:
            self._send(404, b"not found", "text/plain")

    def do_OPTIONS(self):
        self._send(204, b"", "text/plain")

    # -- routing --
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        p = u.path
        try:
            if p == "/api/health":
                return self._json({"ok": True, "time": dse._now()})
            if p == "/api/overview":
                return self._json(overview(int(q.get("buy", [6])[0]), int(q.get("watch", [6])[0])))
            if p == "/api/prices":
                return self._json(prices_table())
            if p == "/api/company":
                code = q.get("code", [""])[0]
                if not code:
                    return self._err("code required", 400)
                return self._json(company(code))
            if p == "/api/portfolio":
                return self._json(portfolio())
            if p == "/api/report":
                return self._json(build_report(int(q.get("buy", [6])[0]), int(q.get("watch", [6])[0])))
            if p.startswith("/reports/"):
                return self._file(os.path.join(REPORTS, os.path.basename(p)), "application/pdf")
            # static webapp
            rel = "index.html" if p in ("/", "") else p.lstrip("/")
            fpath = os.path.join(WEBAPP, rel)
            if os.path.isfile(fpath):
                ext = os.path.splitext(fpath)[1].lower()
                ctype = {".html": "text/html; charset=utf-8", ".js": "text/javascript",
                         ".css": "text/css", ".svg": "image/svg+xml"}.get(ext, "application/octet-stream")
                return self._file(fpath, ctype)
            return self._send(404, b"not found", "text/plain")
        except Exception as e:  # surface scraper/parse errors as JSON
            return self._err(e)

    def do_POST(self):
        u = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            if u.path == "/api/portfolio":
                return self._json(save_portfolio(body.get("holdings", [])))
            return self._err("unknown endpoint", 404)
        except Exception as e:
            return self._err(e)


def main():
    ap = argparse.ArgumentParser(description="DSE dashboard server")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    os.makedirs(REPORTS, exist_ok=True)
    url = f"http://localhost:{args.port}"
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"DSE dashboard -> {url}   (Ctrl+C to stop)")
    if not args.no_open:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
