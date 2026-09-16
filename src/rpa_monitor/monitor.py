from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from .codex_ai import CodexUnavailable, analyze, next_attempt_time
from .config import load_settings
from .retry import automatic_retry
from .roster import workday
from .rules import annotate_attention, is_loop_task, normalize_job, task_name
from .storage import housekeeping, read_json, read_ndjson, write_json, write_ndjson
from .yingdao import YingdaoClient


def _iso_now() -> str:
    return datetime.now().astimezone().isoformat()


def _within_window(now: datetime, settings: dict) -> bool:
    start = datetime.strptime(settings["start_time"], "%H:%M").time()
    end = datetime.strptime(settings["end_time"], "%H:%M").time()
    return start <= now.time().replace(tzinfo=None) <= end


def _merge(existing: list[dict], incoming: list[dict]) -> list[dict]:
    by_id = {str(x.get("jobUuid")): normalize_job(x) for x in existing if x.get("jobUuid")}
    for row in incoming:
        key = str(row.get("jobUuid", ""))
        if key:
            old = by_id.get(key, {})
            old.update(row)
            by_id[key] = normalize_job(old)
    return sorted(by_id.values(), key=lambda x: str(x.get("triggerTime", "")), reverse=True)


def _screenshot_url(detail: dict) -> str:
    for key in ("errorScreenshot", "screenshotUrl", "errorScreenshotUrl", "imageUrl"):
        if detail.get(key):
            return str(detail[key])
    for item in detail.get("screenshots", []) or []:
        if isinstance(item, str): return item
        if isinstance(item, dict) and (item.get("url") or item.get("downloadUrl")):
            return str(item.get("url") or item.get("downloadUrl"))
    return ""


def _upsert_anomalies(rows: list[dict], previous: list[dict]) -> list[dict]:
    by_id = {str(x.get("job", {}).get("jobUuid")): x for x in previous}
    now = _iso_now()
    for job in rows:
        if str(job.get("statusCn")) != "异常" and str(job.get("status", "")).lower() not in ("error", "failed", "fail", "timeout"):
            continue
        key = str(job.get("jobUuid"))
        record = by_id.get(key, {"firstSeenAt": now, "resolved": False})
        record.update({"job": job, "lastSeenAt": now, "needsAttention": bool(job.get("needsAttention")), "isLoopTask": bool(job.get("isLoopTask"))})
        record.setdefault("handlingStatus", "resolved" if record.get("resolved") else "pending")
        if job.get("isLoopTask"):
            record["aiState"] = "skipped_loop"
        elif not job.get("needsAttention"):
            record["aiState"] = "filtered"
        else:
            record.setdefault("aiState", "pending")
        by_id[key] = record
    return sorted(by_id.values(), key=lambda x: str(x.get("job", {}).get("triggerTime", "")), reverse=True)


def _analyze_pending(anomalies: list[dict], rows: list[dict], settings: dict) -> tuple[list[dict], list[dict]]:
    notices: list[dict] = []
    now = datetime.now().astimezone()
    for record in anomalies:
        job = record.get("job", {})
        if record.get("handlingStatus") in ("resolved", "ignored") or record.get("resolved") or not record.get("needsAttention") or is_loop_task(task_name(job)):
            continue
        state = record.get("aiState", "pending")
        retry_at = record.get("nextAiAttempt", "")
        if state == "done": continue
        if retry_at:
            try:
                if datetime.fromisoformat(retry_at) > now: continue
            except ValueError: pass
        try:
            result = analyze(job, str(job.get("screenshotPath", "")))
            record.update({"aiState": "done", "analysis": result, "nextAiAttempt": ""})
            if settings.get("ai_auto_retry", False):
                record["autoRetry"] = automatic_retry(job, settings, rows, result)
            notices.append({"type": "analysis", "jobUuid": job.get("jobUuid"), "title": task_name(job), "message": result.get("summary", "AI分析完成")})
        except CodexUnavailable as exc:
            record.update({"aiState": "failed_waiting", "aiError": str(exc), "nextAiAttempt": next_attempt_time()})
            notices.append({"type": "ai_failed", "jobUuid": job.get("jobUuid"), "title": task_name(job), "message": "AI分析失败，已转人工判断，30分钟后自动重试分析"})
        except Exception as exc:
            record.update({"aiState": "failed_waiting", "aiError": str(exc), "nextAiAttempt": next_attempt_time()})
            notices.append({"type": "ai_failed", "jobUuid": job.get("jobUuid"), "title": task_name(job), "message": "AI分析失败，已转人工判断"})
    return anomalies, notices


def run_scan(force: bool = False, analyze_ai: bool = True) -> dict:
    housekeeping()
    settings = load_settings()
    now = datetime.now().astimezone()
    if settings.get("paused") and not force:
        result = {"ok": True, "skipped": "paused", "message": "巡检已暂停", "updatedAt": _iso_now()}
        write_json("monitor_status.json", result); return result
    if not force and not _within_window(now, settings):
        result = {"ok": True, "skipped": "outside_window", "message": "当前不在巡检时间段", "updatedAt": _iso_now()}
        write_json("monitor_status.json", result); return result
    if settings.get("read_roster", True) and not force:
        on_duty, roster_state = workday(now.date())
        if on_duty is not True:
            result = {"ok": on_duty is False, "skipped": roster_state, "message": "当天未排班，已跳过" if on_duty is False else "排班读取失败，已停止本次巡检", "updatedAt": _iso_now()}
            write_json("monitor_status.json", result); return result

    state = read_json("monitor_state.json", {})
    first_full = state.get("fullScanDate") != now.date().isoformat()
    begin = (now - timedelta(days=1)).replace(hour=17, minute=30, second=0, microsecond=0)
    client = YingdaoClient()
    incoming = client.list_jobs(begin.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d %H:%M:%S"), full=first_full, size=100 if first_full else 50)
    rows = _merge(read_json("run_records.json", []), incoming)
    rows = annotate_attention(rows)

    known = {str(x.get("job", {}).get("jobUuid")) for x in read_ndjson("anomalies.ndjson")}
    for job in rows:
        is_error = str(job.get("statusCn")) == "异常" or str(job.get("status", "")).lower() in ("error", "failed", "fail", "timeout")
        if is_error and str(job.get("jobUuid")) not in known:
            try:
                detail = client.query_job(str(job.get("jobUuid")))
                job.update(detail)
                url = _screenshot_url(detail)
                if url:
                    try: job["screenshotPath"] = client.download_screenshot(url, str(job.get("jobUuid")))
                    except Exception as exc: job["screenshotError"] = str(exc)
            except Exception as exc:
                job["detailQueryError"] = str(exc)

    write_json("run_records.json", rows)
    anomalies = _upsert_anomalies(rows, read_ndjson("anomalies.ndjson"))
    notices: list[dict] = [
        {"type": "new_error", "jobUuid": x.get("job", {}).get("jobUuid"), "title": task_name(x.get("job", {})), "message": "发现新的需关注异常"}
        for x in anomalies if x.get("needsAttention") and not x.get("resolved") and str(x.get("job", {}).get("jobUuid")) not in known
    ]
    if analyze_ai:
        anomalies, ai_notices = _analyze_pending(anomalies, rows, settings)
        notices.extend(ai_notices)
    write_ndjson("anomalies.ndjson", anomalies)
    state.update({"fullScanDate": now.date().isoformat(), "lastScanAt": _iso_now(), "lastCount": len(incoming)})
    write_json("monitor_state.json", state)
    result = {"ok": True, "firstFull": first_full, "fetched": len(incoming), "records": len(rows), "anomalies": len(anomalies), "attention": sum(1 for x in anomalies if x.get("needsAttention") and not x.get("resolved")), "notifications": notices, "updatedAt": _iso_now()}
    write_json("monitor_status.json", result)
    return result
