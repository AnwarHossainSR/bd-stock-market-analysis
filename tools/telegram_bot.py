#!/usr/bin/env python3
"""Telegram bot wrapper for the DSE analysis pipeline.

Run locally or on a small VPS:
    copy .env.example .env
    # edit .env
    .venv/Scripts/python tools/telegram_bot.py

Commands:
    /id
    /health
    /analysis
    /analysis --buy 8 --watch 6 --cash 36600.98 --investor B10526

The bot does not auto-trade. It only sends educational decision-support output.
"""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import dse  # noqa: E402
import health  # noqa: E402
import report  # noqa: E402


def load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_dotenv()

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
API = f"https://api.telegram.org/bot{TOKEN}"
PORTFOLIO_CSV = ROOT / "data" / "portfolio.csv"
DISCLAIMER = "Data scraped from dsebd.org (delayed/EOD). Educational only, NOT financial advice. Verify on DSE before trade."
CONFLICT_HELP = (
    "Telegram 409 conflict: another getUpdates poller or webhook is already using this bot token. "
    "Stop the other bot process, or clear the webhook, then start this bot again."
)


def redact_token(text: object) -> str:
    value = str(text)
    if TOKEN:
        value = value.replace(TOKEN, "<redacted-token>")
    return value


def _allowed_chat_ids() -> set[int]:
    raw = os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "").strip()
    if not raw:
        return set()
    return {int(x.strip()) for x in raw.split(",") if x.strip()}


ALLOWED_CHAT_IDS = _allowed_chat_ids()


def _request(method: str, payload=None, files=None, timeout=60):
    resp = requests.post(f"{API}/{method}", data=payload or {}, files=files, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def send_message(chat_id: int, text: str):
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [""]
    for chunk in chunks:
        _request("sendMessage", {"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True})


def send_document(chat_id: int, path: str | Path, caption: str = ""):
    with open(path, "rb") as f:
        _request("sendDocument", {"chat_id": chat_id, "caption": caption[:1024]}, {"document": f}, timeout=180)


def parse_analysis_args(text: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--buy", type=int, default=int(os.environ.get("ANALYSIS_BUY", 6)))
    parser.add_argument("--watch", type=int, default=int(os.environ.get("ANALYSIS_WATCH", 6)))
    parser.add_argument("--cash", type=float, default=float(os.environ.get("ANALYSIS_CASH", 0)))
    parser.add_argument("--investor", default=os.environ.get("ANALYSIS_INVESTOR"))
    parts = shlex.split(text)
    args = parts[1:] if parts and parts[0].split("@", 1)[0] == "/analysis" else []
    return parser.parse_args(args)


def maybe_git_pull() -> str | None:
    if os.environ.get("TELEGRAM_BOT_GIT_PULL", "").lower() not in {"1", "true", "yes"}:
        return None
    proc = subprocess.run(
        ["git", "pull", "--ff-only"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
    )
    return (proc.stdout + proc.stderr).strip()


def brief(data: dict, health_result: dict, pdf_path: str | Path) -> str:
    breadth = data["breadth"]
    buy = data.get("buy") or []
    watch = data.get("watch") or []
    avoid = data.get("avoid") or []

    lines = [
        "DSE Analysis Complete",
        "",
        f"Market: {data['regime']}",
        f"Breadth: {breadth['adv']} advances / {breadth['dec']} declines / {breadth['total']} total",
        f"Value: {breadth['value_mn']} mn",
        f"Data health: {health_result['status']} | zero-LTP: {health_result['zero_ltp']} | DB latest: {health_result.get('db_latest_date') or 'n/a'}",
        "",
        "BUY-WATCH:",
    ]
    if buy:
        for row in buy[:5]:
            lines.append(
                f"- {row['code']} | LTP {row.get('ltp')} | {(row.get('pct') or 0):+.2f}% | "
                f"{row.get('value_mn') or 0:.3f}mn | {row.get('reason', '')}"
            )
    else:
        lines.append("- Nothing clean today.")

    lines.append("")
    lines.append("WATCH:")
    if watch:
        for row in watch[:5]:
            lines.append(
                f"- {row['code']} | LTP {row.get('ltp')} | {(row.get('pct') or 0):+.2f}% | "
                f"{row.get('value_mn') or 0:.3f}mn | {row.get('reason', '')}"
            )
    else:
        lines.append("- Nothing on watch.")

    if avoid:
        lines.append("")
        lines.append("AVOID / RISK:")
        for row in avoid[:5]:
            lines.append(f"- {row['code']} | {(row.get('pct') or 0):+.2f}% | {row.get('reason', '')}")

    lines.extend(["", f"PDF: {Path(pdf_path).name}", DISCLAIMER])
    return "\n".join(lines)


def run_analysis(text: str) -> tuple[str, Path]:
    args = parse_analysis_args(text)
    maybe_git_pull()

    # Force a fresh whole-market fetch first; report.py will then reuse the newly written short TTL cache.
    dse.get_prices(ttl=0)
    data = report.select(args.buy, args.watch)
    port = report.load_portfolio(str(PORTFOLIO_CSV))
    pdf_path = Path(report.build_pdf(data, port, datetime.now(), investor=args.investor, cash=args.cash))
    health_result = health.check_health(portfolio_path=PORTFOLIO_CSV)
    return brief(data, health_result, pdf_path), pdf_path


def command_health() -> str:
    result = health.check_health(portfolio_path=PORTFOLIO_CSV)
    warnings = ", ".join(result["warnings"]) or "none"
    return (
        f"Data health: {result['status']}\n"
        f"Rows: {result['rows']}\n"
        f"Zero-LTP: {result['zero_ltp']}\n"
        f"DB latest: {result.get('db_latest_date') or 'n/a'}\n"
        f"Warnings: {warnings}\n"
        f"{DISCLAIMER}"
    )


def is_allowed(chat_id: int) -> bool:
    return not ALLOWED_CHAT_IDS or chat_id in ALLOWED_CHAT_IDS


def handle_message(message: dict):
    chat_id = message.get("chat", {}).get("id")
    text = (message.get("text") or "").strip()
    if not chat_id or not text:
        return

    if not is_allowed(chat_id):
        send_message(chat_id, "Unauthorized chat. Ask the bot owner to add this chat id.")
        return

    command = text.split()[0].split("@", 1)[0].lower()
    try:
        if command in {"/start", "/help"}:
            warning = "" if ALLOWED_CHAT_IDS else "\nWarning: TELEGRAM_ALLOWED_CHAT_IDS is not set, so any chat with this bot token can run commands."
            send_message(
                chat_id,
                "Commands:\n"
                "/id - show this chat id\n"
                "/health - check data health\n"
                "/analysis - generate DSE PDF + brief\n"
                "/analysis --buy 8 --watch 6 --cash 36600.98 --investor B10526"
                f"{warning}",
            )
        elif command == "/id":
            send_message(chat_id, f"Chat id: {chat_id}")
        elif command == "/health":
            send_message(chat_id, command_health())
        elif command == "/analysis":
            send_message(chat_id, "Running DSE analysis. This can take a minute...")
            text_brief, pdf_path = run_analysis(text)
            send_message(chat_id, text_brief)
            send_document(chat_id, pdf_path, "DSE analysis PDF")
        else:
            send_message(chat_id, "Unknown command. Send /help")
    except SystemExit:
        send_message(chat_id, "Invalid /analysis arguments. Example: /analysis --buy 6 --watch 6")
    except Exception as exc:
        send_message(chat_id, f"Command failed: {type(exc).__name__}: {exc}")


def poll():
    if not TOKEN:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN first.")
    offset = None
    print("Telegram bot started. Press Ctrl+C to stop.", flush=True)
    while True:
        params = {"timeout": 50}
        if offset is not None:
            params["offset"] = offset
        try:
            resp = requests.get(f"{API}/getUpdates", params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                time.sleep(3)
                continue
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message") or update.get("edited_message")
                if message:
                    handle_message(message)
        except KeyboardInterrupt:
            print("\nTelegram bot stopped.", flush=True)
            return
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status == 409:
                print(CONFLICT_HELP, file=sys.stderr)
            else:
                print(f"poll error: HTTPError: {redact_token(exc)}", file=sys.stderr)
            time.sleep(5)
        except Exception as exc:
            print(f"poll error: {type(exc).__name__}: {redact_token(exc)}", file=sys.stderr)
            time.sleep(5)


if __name__ == "__main__":
    try:
        poll()
    except KeyboardInterrupt:
        print("\nTelegram bot stopped.", flush=True)
