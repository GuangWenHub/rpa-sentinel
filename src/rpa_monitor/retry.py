from __future__ import annotations

from datetime import datetime
from .rules import retry_guards
from .storage import read_json, write_json
from .yingdao import YingdaoClient


def _chains() -> dict: return read_json("retry_chains.json", {})


def chain_for(job_uuid: str) -> tuple[str, dict]:
    chains = _chains()
    for root, chain in chains.items():
        if root == job_uuid or chain.get("current_job_uuid") == job_uuid or any(x.get("job_uuid") == job_uuid or x.get("new_job_uuid") == job_uuid for x in chain.get("history", [])):
            return root, chain
    return job_uuid, {"root_job_uuid": job_uuid, "current_job_uuid": job_uuid, "attempts": 0, "history": []}


def retry_count(job_uuid: str) -> int: return int(chain_for(job_uuid)[1].get("attempts", 0))


def _execute(job: dict, mode: str, settings: dict) -> dict:
    root, chain = chain_for(str(job.get("jobUuid"))); maximum = int(settings.get("max_auto_retries", 2))
    if int(chain.get("attempts", 0)) >= maximum: raise RuntimeError(f"已达到最大重试次数 {maximum}")
    data = YingdaoClient().retry_job(str(job.get("jobUuid")))
    new_uuid = str(data.get("jobUuid") or data.get("newJobUuid") or "")
    chain["attempts"] = int(chain.get("attempts", 0)) + 1; chain["current_job_uuid"] = new_uuid or str(job.get("jobUuid"))
    chain.setdefault("history", []).append({"attempt": chain["attempts"], "mode": mode, "job_uuid": str(job.get("jobUuid")), "new_job_uuid": new_uuid, "submitted_at": datetime.now().astimezone().isoformat()})
    chains = _chains(); chains[root] = chain; write_json("retry_chains.json", chains)
    return {"accepted": True, "root_job_uuid": root, "attempt": chain["attempts"], "new_job_uuid": new_uuid, "response": data}


def manual_retry(job: dict, settings: dict) -> dict: return _execute(job, "manual", settings)


def automatic_retry(job: dict, settings: dict, all_rows: list[dict], analysis: dict) -> dict:
    count = retry_count(str(job.get("jobUuid"))); reasons = retry_guards(job, settings, all_rows, analysis, count)
    if reasons: return {"accepted": False, "blocked_reasons": reasons, "attempt": count}
    return _execute(job, "ai_auto", settings)
