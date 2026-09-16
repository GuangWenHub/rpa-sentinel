from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from .config import AUTOMATION_DIR, ENV_FILE, PROJECT_DIR, env
from .rules import is_loop_task, normalize_job, task_name

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SCHEMA = AUTOMATION_DIR / "config" / "ai_analysis.schema.json"


class CodexUnavailable(RuntimeError): pass


def _failure_message(output: str) -> str:
    low = output.lower()
    if any(value in low for value in ("usage limit", "rate limit", "quota", "额度", "insufficient")):
        return "Codex额度或频率限制，30分钟后重试分析"
    if "no rollout found" in low or "thread/resume failed" in low:
        return "配置的 CODEX_SESSION_ID 不是可续接的 Codex exec 会话，请重新配置专用分析会话"
    if "not logged in" in low or "authentication" in low or "unauthorized" in low:
        return "Codex CLI 未登录或登录状态已失效"
    compact = " ".join(output.strip().splitlines())
    return "Codex分析失败：" + (compact[-500:] or "未返回错误详情")


def _replace_env_value(content: str, name: str, value: str) -> str:
    lines = content.splitlines()
    replacement = f"{name}={value}"
    for index, line in enumerate(lines):
        if line.strip().startswith(name + "="):
            lines[index] = replacement
            break
    else:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(replacement)
    return "\n".join(lines) + "\n"


def initialize_analysis_session() -> dict:
    """创建专用 Codex exec 会话并只替换 .env 中的会话 ID。"""
    codex = env("CODEX_CLI_PATH", "codex")
    model = env("CODEX_MODEL", "gpt-5.6-luna")
    prompt = (
        "建立一个RPA异常只读分析专用会话。今后的消息会提供单条影刀运行异常证据。"
        "你只分析事实、可能原因、人工处理建议、证据是否充分和重试风险；"
        "不调用工具，不修改文件，不执行或重试任务。"
        "本次是初始化验证，请按指定JSON Schema分析一条脱敏样例：任务=会话初始化检查，状态=error，错误=测试连接。"
    )
    with tempfile.TemporaryDirectory(prefix="rpa_codex_init_") as temp_dir:
        output = Path(temp_dir) / "analysis.json"
        command = [
            codex, "exec", "-m", model, "-s", "read-only", "--skip-git-repo-check",
            "--json", "--output-schema", str(SCHEMA), "-o", str(output), "-",
        ]
        try:
            result = subprocess.run(
                command, cwd=str(PROJECT_DIR), input=prompt, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=300, creationflags=NO_WINDOW,
            )
        except FileNotFoundError as exc:
            raise CodexUnavailable("找不到本机 Codex CLI，请检查 CODEX_CLI_PATH") from exc
        except subprocess.TimeoutExpired as exc:
            raise CodexUnavailable("Codex会话初始化超过5分钟，已停止等待") from exc
        combined = (result.stdout or "") + "\n" + (result.stderr or "")
        if result.returncode:
            raise CodexUnavailable(_failure_message(combined))
        session_id = ""
        for line in (result.stdout or "").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "thread.started":
                session_id = str(event.get("thread_id") or event.get("threadId") or "")
                break
        if not session_id:
            raise CodexUnavailable("Codex已响应，但未返回可保存的会话 ID")
        try:
            analysis = json.loads(output.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            raise CodexUnavailable("Codex初始化结果不是有效JSON") from exc
    old = ENV_FILE.read_text(encoding="utf-8-sig") if ENV_FILE.exists() else ""
    temp_env = ENV_FILE.with_suffix(".tmp")
    temp_env.write_text(_replace_env_value(old, "CODEX_SESSION_ID", session_id), encoding="utf-8")
    temp_env.replace(ENV_FILE)
    return {"ok": True, "model": model, "schemaValidated": isinstance(analysis, dict)}


def analyze(job: dict, screenshot_path: str = "") -> dict:
    normalize_job(job)
    if job.get("isLoopTask") or is_loop_task(task_name(job)):
        raise ValueError("循环任务按规则不调用 Codex")
    session_id = env("CODEX_SESSION_ID")
    if not session_id: raise CodexUnavailable(".env 缺少 CODEX_SESSION_ID")
    codex = env("CODEX_CLI_PATH", "codex")
    model = env("CODEX_MODEL", "gpt-5.6-luna")
    evidence = {
        "jobUuid": job.get("jobUuid"), "taskName": task_name(job),
        "taskType": job.get("taskTypeCn"), "isAdvancedTask": job.get("isAdvancedTask"),
        "status": job.get("status"), "statusCn": job.get("statusCn"),
        "triggerTime": job.get("triggerTime"), "updateTime": job.get("updateTime"),
        "robotClientName": job.get("robotClientName"), "robotName": job.get("robotName"),
        "remark": job.get("remark"), "message": job.get("message"),
        "detailQueryError": job.get("detailQueryError"), "screenshotError": job.get("screenshotError"),
        "screenshotAttached": bool(screenshot_path and Path(screenshot_path).exists()),
    }
    prompt = (
        "你是RPA异常只读分析助手。这是影刀异常巡检程序提交的分析请求。"
        "只依据本条证据分析，禁止调用任何工具，禁止读取或修改文件，禁止执行或重试任务。"
        "summary写明已观察到的报错事实；likely_causes只能写可能原因，不得伪装成已确认根因；"
        "suggestions给出人工可执行的排查与处理建议；证据不足时明确缺什么。"
        "allow_retry只表示建议，不代表已经重试。仅按指定JSON Schema返回，不要附加Markdown。"
        "异常证据：" + json.dumps(evidence, ensure_ascii=False)
    )
    with tempfile.TemporaryDirectory(prefix="rpa_codex_") as temp_dir:
        output = Path(temp_dir) / "analysis.json"
        command = [
            codex, "exec", "resume", "-m", model,
            "-c", 'sandbox_mode="read-only"', "--skip-git-repo-check",
            "--output-schema", str(SCHEMA), "-o", str(output),
        ]
        if screenshot_path and Path(screenshot_path).exists():
            command += ["-i", screenshot_path]
        command += [session_id, "-"]
        try:
            result = subprocess.run(
                command, cwd=str(PROJECT_DIR), input=prompt, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=300, creationflags=NO_WINDOW,
            )
        except FileNotFoundError as exc:
            raise CodexUnavailable("找不到本机 Codex CLI，请检查 CODEX_CLI_PATH") from exc
        except subprocess.TimeoutExpired as exc:
            raise CodexUnavailable("Codex分析超过5分钟，已停止等待") from exc
        combined = (result.stdout or "") + "\n" + (result.stderr or "")
        if result.returncode:
            raise CodexUnavailable(_failure_message(combined))
        try:
            analysis = json.loads(output.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            raise CodexUnavailable("Codex结果不是有效JSON") from exc
    required = {"summary", "likely_causes", "suggestions", "evidence_sufficient", "allow_retry", "retry_reason", "risk"}
    if not required.issubset(analysis):
        raise CodexUnavailable("Codex结果缺少必要分析字段")
    analysis["analyzed_at"] = datetime.now().astimezone().isoformat()
    analysis["model"] = model
    return analysis


def next_attempt_time() -> str: return (datetime.now().astimezone() + timedelta(minutes=30)).isoformat()
