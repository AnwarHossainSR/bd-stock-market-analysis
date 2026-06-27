"""Persist generated analysis runs for the dashboard."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

DISCLAIMER = "Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice."
ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "reports" / "analysis_runs"


def _runs_dir(runs_dir: str | Path | None = None) -> Path:
    return Path(runs_dir) if runs_dir is not None else RUNS_DIR


def _run_path(run_id: str, runs_dir: str | Path | None = None) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", run_id)
    return _runs_dir(runs_dir) / f"{safe}.json"


def _new_id(now: datetime | None = None) -> str:
    dt = now or datetime.now()
    return f"{dt.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def summarize_payload(payload: dict, report_status: str = "ok") -> str:
    market = payload.get("market") or {}
    breadth = market.get("breadth") or {}
    screen = payload.get("screen") or {}
    report = payload.get("report") or {}
    lines = [
        "# DSE Analysis Run",
        "",
        f"Fetched: {payload.get('fetched_at', 'n/a')}",
        f"Market: {market.get('regime', 'n/a')} | adv {breadth.get('adv', breadth.get('advances', 'n/a'))} | dec {breadth.get('dec', breadth.get('declines', 'n/a'))} | value {breadth.get('value_mn', breadth.get('total_value_mn', 'n/a'))}mn",
        f"Report: {report_status}" + (f" | {report.get('file')}" if report.get("file") else ""),
        "",
        "## Buy",
    ]
    buys = screen.get("buy") or []
    lines.extend([f"- {x.get('code')} | {x.get('pct', x.get('pct_change', 'n/a'))}% | score {x.get('score', 'n/a')} | {x.get('reason', '')}" for x in buys[:8]] or ["- Nothing clean today."])
    lines.extend(["", "## Watch"])
    watch = screen.get("watch") or []
    lines.extend([f"- {x.get('code')} | {x.get('pct', x.get('pct_change', 'n/a'))}% | {x.get('reason', '')}" for x in watch[:8]] or ["- None."])
    lines.extend(["", "## Avoid"])
    avoid = screen.get("avoid") or []
    lines.extend([f"- {x.get('code')} | {x.get('pct', x.get('pct_change', 'n/a'))}% | {x.get('reason', '')}" for x in avoid[:8]] or ["- None."])
    lines.extend(["", DISCLAIMER])
    return "\n".join(lines)


def save_run(
    payload: dict,
    source: str = "ui",
    summary_md: str | None = None,
    commentary_md: str = "",
    report_status: str = "ok",
    report_error: str | None = None,
    runs_dir: str | Path | None = None,
) -> dict:
    runs_path = _runs_dir(runs_dir)
    runs_path.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now().isoformat(timespec="seconds")
    run_id = _new_id(datetime.fromisoformat(created_at))
    report = payload.get("report") or {}
    market_state = (payload.get("session") or {}).get("market_state") or (payload.get("market") or {}).get("regime")
    record = {
        "id": run_id,
        "created_at": created_at,
        "source": source,
        "market_state": market_state,
        "payload_json": payload,
        "summary_md": summary_md or summarize_payload(payload, report_status=report_status),
        "commentary_md": commentary_md,
        "report_file": report.get("file"),
        "report_url": report.get("url"),
        "report_status": report_status,
        "report_error": report_error,
        "disclaimer": payload.get("disclaimer") or DISCLAIMER,
    }
    _run_path(run_id, runs_path).write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return record


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_runs(limit: int = 20, runs_dir: str | Path | None = None) -> list[dict]:
    path = _runs_dir(runs_dir)
    if not path.exists():
        return []
    records = [r for r in (_read(p) for p in path.glob("*.json")) if r]
    records.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    out = []
    for record in records[:limit]:
        out.append({k: record.get(k) for k in ("id", "created_at", "source", "market_state", "report_file", "report_url", "report_status", "report_error", "disclaimer")})
        out[-1]["summary_md"] = record.get("summary_md")
        out[-1]["commentary_md"] = record.get("commentary_md")
    return out


def get_run(run_id: str, runs_dir: str | Path | None = None) -> dict | None:
    path = _run_path(run_id, runs_dir)
    if not path.exists():
        return None
    return _read(path)


def latest_run(runs_dir: str | Path | None = None) -> dict | None:
    runs = list_runs(limit=1, runs_dir=runs_dir)
    if not runs:
        return None
    return get_run(runs[0]["id"], runs_dir=runs_dir)


def save_commentary(run_id: str, commentary_md: str, runs_dir: str | Path | None = None) -> dict | None:
    record = get_run(run_id, runs_dir=runs_dir)
    if not record:
        return None
    record["commentary_md"] = commentary_md
    record["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _run_path(run_id, runs_dir).write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return record
