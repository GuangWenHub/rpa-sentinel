from __future__ import annotations

import json
import subprocess
from datetime import date
from .config import env
from .storage import read_json, write_json

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def workday(day: date) -> tuple[bool | None, str]:
    cache = read_json("roster_cache.json", {})
    if cache.get("date") == day.isoformat(): return cache.get("workday"), "cached_roster"
    script = env("LARK_CLI_PS1", r"C:\Users\GA-XFKJ\AppData\Roaming\npm\lark-cli.ps1")
    calendar = env("YINGDAO_ROSTER_CALENDAR_ID")
    if not calendar: return None, "missing_roster_calendar_id"
    command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, "calendar", "+agenda", "--as", "user", "--calendar-id", calendar, "--start", day.isoformat(), "--end", day.isoformat(), "--format", "json"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=45, creationflags=NO_WINDOW)
    if result.returncode:
        low = ((result.stderr or "") + (result.stdout or "")).lower()
        return None, "feishu_auth_expired" if "token_missing" in low or "need_user_authorization" in low else "feishu_calendar_unavailable"
    payload = json.loads(result.stdout); events = payload.get("data", payload)
    if isinstance(events, dict): events = events.get("events", events.get("items", []))
    value = any(any(k in str(x.get("summary", x.get("title", ""))) for k in ("排班", "班次", "上班", "值班", "工作日")) and not any(k in str(x.get("summary", x.get("title", ""))) for k in ("休息", "休假")) for x in events if isinstance(x, dict))
    write_json("roster_cache.json", {"date": day.isoformat(), "workday": value}); return value, "roster_checked"
