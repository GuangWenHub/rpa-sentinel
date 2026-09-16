from __future__ import annotations

import json
import shutil
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
AUTOMATION_DIR = SRC_DIR.parent
PROJECT_DIR = AUTOMATION_DIR
DATA_DIR = AUTOMATION_DIR / "data"
SCREENSHOT_DIR = DATA_DIR / "screenshots"
ENV_FILE = AUTOMATION_DIR / ".env"
SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "read_roster": True, "start_time": "08:00", "end_time": "17:30", "frequency_minutes": 10,
    "ai_auto_retry": False, "max_auto_retries": 2, "block_if_same_task_running": True,
    "block_high_risk_keywords": True, "block_if_evidence_insufficient": True,
    "require_recent_success": True, "retry_timeout_minutes": 45,
    "retry_block_keywords": ["订单", "采购", "付款", "支付", "库存写入", "补货"],
    "retry_blacklist": [], "hidden_columns": [],
}


def ensure_layout() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True); SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("anomalies.ndjson", "monitor_state.json", "monitor_status.json", "roster_cache.json", "run_records.json"):
        old, new = AUTOMATION_DIR / name, DATA_DIR / name
        if old.exists() and not new.exists(): shutil.copy2(old, new)


def read_dotenv() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_FILE.exists(): return values
    for raw in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        key, value = line.split("=", 1); value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'": value = value[1:-1]
        values[key.strip()] = value
    return values


def env(name: str, default: str = "") -> str: return read_dotenv().get(name, default)


def load_settings() -> dict:
    ensure_layout(); result = dict(DEFAULT_SETTINGS)
    try:
        saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8-sig"))
        if isinstance(saved, dict): result.update(saved)
    except Exception: pass
    return result


def save_settings(value: dict) -> None:
    ensure_layout(); merged = dict(DEFAULT_SETTINGS); merged.update(value)
    temp = SETTINGS_FILE.with_suffix(".tmp"); temp.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"); temp.replace(SETTINGS_FILE)


ensure_layout()
