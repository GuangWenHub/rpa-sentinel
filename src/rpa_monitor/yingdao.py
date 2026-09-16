from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen
from .config import SCREENSHOT_DIR, env
from .rules import normalize_job


STATUS_CN = {
    "running": "运行中", "waiting": "等待调度", "wait": "等待调度", "pending": "等待调度", "queued": "等待调度",
    "finish": "完成", "finished": "完成", "success": "完成", "completed": "完成",
    "stopping": "停止中", "cancelling": "停止中", "canceling": "停止中",
    "stop": "已停止", "stopped": "已停止", "cancel": "已停止", "cancelled": "已停止", "canceled": "已停止",
    "error": "异常", "failed": "异常", "fail": "异常", "timeout": "异常",
}


def status_cn(value) -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    return STATUS_CN.get(raw, str(value or "未知"))


class YingdaoClient:
    def __init__(self):
        self.base = env("YINGDAO_API_BASE_URL", "https://api.yingdao.com").rstrip("/")
        self.key_id = env("YINGDAO_ACCESS_KEY_ID")
        self.key_secret = env("YINGDAO_ACCESS_KEY_SECRET")
        if not self.key_id or not self.key_secret: raise RuntimeError(".env 缺少影刀 API 配置")
        self._token = ""

    def _post(self, path: str, payload: dict, auth: bool = True) -> dict:
        headers = {"Content-Type": "application/json"}
        if auth: headers["Authorization"] = "Bearer " + self.token()
        req = Request(self.base + path, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers=headers)
        with urlopen(req, timeout=45) as response: result = json.loads(response.read().decode("utf-8"))
        if not result.get("success") or result.get("code") not in (None, 0, 200):
            raise RuntimeError(f"影刀接口失败 code={result.get('code')} message={result.get('message') or result.get('msg') or 'unknown'}")
        return result

    def token(self) -> str:
        if self._token: return self._token
        body = ("accessKeyId=" + self.key_id + "&accessKeySecret=" + self.key_secret).encode("utf-8")
        req = Request(self.base + "/oapi/token/v2/token/create", data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urlopen(req, timeout=30) as response: result = json.loads(response.read().decode("utf-8"))
        if not result.get("success") or not result.get("data", {}).get("accessToken"): raise RuntimeError("影刀鉴权失败")
        self._token = result["data"]["accessToken"]; return self._token

    def list_jobs(self, begin: str, end: str, full: bool = True, size: int = 100) -> list[dict]:
        cursor, rows = "", []
        while True:
            body = {"triggerTimeBegin": begin, "triggerTimeEnd": end, "cursorDirection": "next", "cursorId": cursor, "size": min(size, 100), "queryApi": False}
            data = (self._post("/oapi/dispatch/v2/job/list", body).get("data") or {})
            for job in data.get("dataList") or []: job["statusCn"] = status_cn(job.get("status")); rows.append(normalize_job(job))
            next_id = data.get("nextId")
            if not full or not data.get("hasData") or not next_id or next_id == cursor: break
            cursor = next_id
        return rows

    def query_job(self, job_uuid: str) -> dict:
        job = self._post("/oapi/dispatch/v2/job/query", {"jobUuid": job_uuid}).get("data") or {}
        job["statusCn"] = status_cn(job.get("status")); return normalize_job(job)

    def retry_job(self, job_uuid: str) -> dict:
        return self._post("/oapi/dispatch/v2/job/retry", {"jobUuid": job_uuid}).get("data") or {}

    def download_screenshot(self, url: str, job_uuid: str) -> str:
        if not url: return ""
        path = SCREENSHOT_DIR / f"{job_uuid}.png"
        req = Request(url, headers={"User-Agent": "RPA-Monitor/2.0"})
        with urlopen(req, timeout=45) as response: path.write_bytes(response.read())
        return str(path)
