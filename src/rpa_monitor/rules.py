from __future__ import annotations

from collections import defaultdict

LOOP_PREFIXES = ("10min_", "20min_")
HANDLING_STATUSES = ("pending", "resolved", "ignored")


def is_loop_task(name: str) -> bool: return str(name or "").startswith(LOOP_PREFIXES)


def task_name(job: dict) -> str:
    """高级任务的 job/list 记录可能没有 taskName，以 robotName 作为显示名称。"""
    return str(job.get("taskName") or job.get("displayTaskName") or job.get("robotName") or "未命名任务").strip()


def normalize_job(job: dict) -> dict:
    raw_task_name = str(job.get("taskName") or "").strip()
    robot_name = str(job.get("robotName") or "").strip()
    advanced = not raw_task_name and bool(robot_name)
    job["displayTaskName"] = raw_task_name or robot_name or "未命名任务"
    job["isAdvancedTask"] = advanced
    job["taskTypeCn"] = "高级任务" if advanced else "普通任务"
    return job


def filter_anomaly_view(rows: list[dict], view: str) -> list[dict]:
    """需关注视图保留已解决记录，由界面灰显；只有回收站操作才移除。"""
    if view == "attention":
        return [row for row in rows if row.get("needsAttention")]
    return rows


def apply_handling_status(rows: list[dict], job_uuid: str, value: str) -> bool:
    """更新展示处理状态；已解决和无需处理都保留原异常记录。"""
    if value not in HANDLING_STATUSES:
        raise ValueError("无效的处理状态")
    for row in rows:
        if str(row.get("job", {}).get("jobUuid")) == str(job_uuid):
            row["handlingStatus"] = value
            row["resolved"] = value == "resolved"
            return True
    return False


def annotate_attention(rows: list[dict]) -> list[dict]:
    """按 taskName + robotUuid 计算连续异常；循环任务第5次起才需关注。"""
    counters: dict[str, int] = defaultdict(int)
    ordered = sorted(rows, key=lambda x: str(x.get("triggerTime", "")))
    for row in ordered:
        normalize_job(row)
        name = task_name(row)
        key = name + "|" + str(row.get("robotUuid", ""))
        error = str(row.get("status", "")).lower() == "error"
        counters[key] = counters[key] + 1 if error else 0
        loop = is_loop_task(name)
        row["isLoopTask"] = loop
        row["consecutiveErrorCount"] = counters[key] if error else 0
        row["needsAttention"] = bool(error and (not loop or counters[key] >= 5))
        row["aiEligible"] = bool(row["needsAttention"] and not loop)
    return rows


def retry_guards(job: dict, settings: dict, all_rows: list[dict], analysis: dict, retry_count: int) -> list[str]:
    reasons: list[str] = []
    name = task_name(job); job_uuid = str(job.get("jobUuid", ""))
    if is_loop_task(name): reasons.append("循环任务禁止自动重试")
    if name in settings.get("retry_blacklist", []): reasons.append("任务位于自动重试黑名单")
    if retry_count >= int(settings.get("max_auto_retries", 2)): reasons.append("已达到最大自动重试次数")
    if settings.get("block_if_same_task_running", True) and any(task_name(x) == name and str(x.get("status", "")).lower() == "running" and str(x.get("jobUuid")) != job_uuid for x in all_rows): reasons.append("同名任务正在运行")
    if settings.get("block_high_risk_keywords", True) and any(word in name or word in str(job.get("remark", "")) for word in settings.get("retry_block_keywords", [])): reasons.append("命中高重复风险关键词")
    if settings.get("block_if_evidence_insufficient", True) and not analysis.get("evidence_sufficient", False): reasons.append("AI判断证据不足")
    if settings.get("require_recent_success", True):
        same_task = [x for x in sorted(all_rows, key=lambda r: str(r.get("triggerTime", "")), reverse=True)
                     if task_name(x) == name and str(x.get("jobUuid", "")) != job_uuid]
        recent = same_task[:3]
        if not recent or not any(str(x.get("statusCn", "")) == "完成" or str(x.get("status", "")).lower() in ("finish", "finished", "success", "completed") for x in recent):
            reasons.append("近期同名任务没有成功记录")
    if not analysis.get("allow_retry", False): reasons.append("AI未建议重试")
    return reasons
