"""Matplotlib chart renderers for PDF embedding. Headless via Agg."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

NAVY = "#102a43"
BLUE = "#3b82f6"
GREEN = "#16a34a"
AMBER = "#f59e0b"
GREY = "#94a3b8"
RED = "#dc2626"


def _save(fig, path):
    fig.savefig(path, dpi=110, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def price_chart(hist, ind, out_path):
    closes = [r["close"] for r in hist if r.get("close") is not None]
    fig, ax = plt.subplots(figsize=(6, 2.2))
    ax.plot(closes, color=NAVY, lw=1.4, label="Close")

    def ma(n):
        return [sum(closes[i - n + 1 : i + 1]) / n if i >= n - 1 else None for i in range(len(closes))]

    if len(closes) >= 20:
        ax.plot(ma(20), color=BLUE, lw=1.0, label="SMA20")
    if len(closes) >= 50:
        ax.plot(ma(50), color=AMBER, lw=1.0, label="SMA50")
    title = ind.get("trend") if isinstance(ind, dict) else None
    if title:
        ax.set_title(f"Price trend: {title}", fontsize=8)
    ax.legend(fontsize=6, loc="upper left", frameon=False)
    ax.tick_params(labelsize=6)
    ax.set_xticks([])
    ax.grid(alpha=0.15)
    return _save(fig, out_path)


def sector_pie(weights, out_path):
    labels = list(weights.keys()) or ["None"]
    vals = list(weights.values()) or [1]
    fig, ax = plt.subplots(figsize=(3.2, 3.2))
    ax.pie(vals, labels=labels, autopct="%1.0f%%", textprops={"fontsize": 7}, colors=plt.cm.tab20.colors)
    return _save(fig, out_path)


def breadth_bar(breadth, out_path):
    adv = breadth.get("adv", breadth.get("advances", 0))
    dec = breadth.get("dec", breadth.get("declines", 0))
    total = breadth.get("total", breadth.get("total_traded", adv + dec))
    fig, ax = plt.subplots(figsize=(3.2, 2.0))
    ax.bar(["Adv", "Dec", "Unch"], [adv, dec, max(0, total - adv - dec)], color=[GREEN, RED, GREY])
    ax.tick_params(labelsize=7)
    return _save(fig, out_path)


def portfolio_alloc(positions, out_path):
    labels = [p["code"] for p in positions] or ["None"]
    vals = [(p.get("mval") or p.get("market_value") or 0) for p in positions] or [1]
    if sum(vals) <= 0:
        vals = [1 for _ in labels]
    fig, ax = plt.subplots(figsize=(3.2, 3.2))
    ax.pie(vals, labels=labels, autopct="%1.0f%%", textprops={"fontsize": 7}, colors=plt.cm.Set2.colors)
    return _save(fig, out_path)
