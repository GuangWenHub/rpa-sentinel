from __future__ import annotations

import argparse
import json
import sys

from .codex_ai import analyze, initialize_analysis_session
from .config import load_settings, save_settings
from .monitor import run_scan
from .retry import manual_retry
from .rules import apply_handling_status, filter_anomaly_view
from .storage import housekeeping, read_json, read_ndjson, restore, recycle, write_ndjson

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="strict")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _print(value) -> None:
    print(json.dumps(value, ensure_ascii=False))


def _find_job(job_uuid: str) -> dict:
    for row in read_json("run_records.json", []):
        if str(row.get("jobUuid")) == job_uuid: return row
    raise RuntimeError("未找到运行记录")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan"); scan.add_argument("--force", action="store_true"); scan.add_argument("--no-ai", action="store_true")
    sub.add_parser("settings-get")
    save = sub.add_parser("settings-save"); save.add_argument("json")
    data = sub.add_parser("data"); data.add_argument("--view", choices=("attention", "errors", "all", "recycle"), default="attention")
    ai = sub.add_parser("analyze"); ai.add_argument("--job", required=True)
    sub.add_parser("ai-session-init")
    retry = sub.add_parser("retry"); retry.add_argument("--job", required=True)
    resolve = sub.add_parser("resolve"); resolve.add_argument("--job", required=True); resolve.add_argument("--value", choices=("true", "false"), default="true")
    handle = sub.add_parser("handle"); handle.add_argument("--job", required=True); handle.add_argument("--value", choices=("pending", "resolved", "ignored"), required=True)
    trash = sub.add_parser("recycle"); trash.add_argument("--job", required=True)
    back = sub.add_parser("restore"); back.add_argument("--job", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "scan": _print(run_scan(args.force, not args.no_ai))
        elif args.command == "settings-get": _print(load_settings())
        elif args.command == "settings-save": save_settings(json.loads(args.json)); _print(load_settings())
        elif args.command == "data":
            housekeeping()
            if args.view == "all": rows = read_json("run_records.json", [])
            elif args.view == "recycle": rows = read_ndjson("recycle_bin.ndjson")
            else:
                rows = read_ndjson("anomalies.ndjson")
                rows = filter_anomaly_view(rows, args.view)
            _print(rows)
        elif args.command == "analyze":
            job = _find_job(args.job); result = analyze(job, str(job.get("screenshotPath", "")))
            rows = read_ndjson("anomalies.ndjson")
            for row in rows:
                if str(row.get("job", {}).get("jobUuid")) == args.job: row.update({"analysis": result, "aiState": "done", "nextAiAttempt": ""})
            write_ndjson("anomalies.ndjson", rows); _print(result)
        elif args.command == "ai-session-init": _print(initialize_analysis_session())
        elif args.command == "retry": _print(manual_retry(_find_job(args.job), load_settings()))
        elif args.command == "resolve":
            rows = read_ndjson("anomalies.ndjson")
            value = "resolved" if args.value == "true" else "pending"
            if not apply_handling_status(rows, args.job, value): raise RuntimeError("未找到异常记录")
            write_ndjson("anomalies.ndjson", rows); _print({"ok": True})
        elif args.command == "handle":
            rows = read_ndjson("anomalies.ndjson")
            if not apply_handling_status(rows, args.job, args.value): raise RuntimeError("未找到异常记录")
            write_ndjson("anomalies.ndjson", rows); _print({"ok": True})
        elif args.command == "recycle":
            rows = read_ndjson("anomalies.ndjson"); found = next((x for x in rows if str(x.get("job", {}).get("jobUuid")) == args.job), None)
            if not found: raise RuntimeError("未找到异常记录")
            recycle(found); write_ndjson("anomalies.ndjson", [x for x in rows if str(x.get("job", {}).get("jobUuid")) != args.job]); _print({"ok": True})
        elif args.command == "restore": _print({"ok": restore(args.job)})
        return 0
    except Exception as exc:
        _print({"ok": False, "error": str(exc)}); return 1


if __name__ == "__main__": sys.exit(main())
