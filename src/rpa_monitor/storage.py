from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Iterable
from .config import DATA_DIR, ensure_layout


def read_json(name: str, default):
    ensure_layout(); path = DATA_DIR / name
    try: return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception: return default


def write_json(name: str, value) -> None:
    ensure_layout(); path = DATA_DIR / name; temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"); temp.replace(path)


def read_ndjson(name: str) -> list[dict]:
    ensure_layout(); path = DATA_DIR / name; rows: list[dict] = []
    if not path.exists(): return rows
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        try: rows.append(json.loads(line))
        except Exception: continue
    return rows


def write_ndjson(name: str, rows: Iterable[dict]) -> None:
    ensure_layout(); path = DATA_DIR / name; temp = path.with_suffix(path.suffix + ".tmp")
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows); temp.write_text(text + ("\n" if text else ""), encoding="utf-8"); temp.replace(path)


def append_ndjson(name: str, row: dict) -> None:
    ensure_layout(); path = DATA_DIR / name
    with path.open("a", encoding="utf-8") as stream: stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def recycle(row: dict) -> None:
    value = dict(row); value["recycledAt"] = datetime.now().astimezone().isoformat()
    append_ndjson("recycle_bin.ndjson", value)


def restore(job_uuid: str) -> bool:
    rows = read_ndjson("recycle_bin.ndjson"); found = next((x for x in rows if str(x.get("job", {}).get("jobUuid")) == job_uuid), None)
    if not found: return False
    append_ndjson("anomalies.ndjson", found); write_ndjson("recycle_bin.ndjson", [x for x in rows if str(x.get("job", {}).get("jobUuid")) != job_uuid]); return True


def housekeeping() -> dict:
    """异常保留30天；回收站中的记录保留2天。"""
    now = datetime.now().astimezone(); archive_before = now - timedelta(days=30); purge_before = now - timedelta(days=2)
    def parsed(raw: str):
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return value.astimezone() if value.tzinfo else value.replace(tzinfo=now.tzinfo)
    anomalies = read_ndjson("anomalies.ndjson"); kept, moved = [], []
    for row in anomalies:
        raw = str(row.get("job", {}).get("triggerTime") or row.get("firstSeenAt") or "")
        try: old = parsed(raw) < archive_before
        except Exception: old = False
        if old:
            value = dict(row); value["recycledAt"] = now.isoformat(); value["recycleReason"] = "历史异常超过30天"
            moved.append(value)
        else: kept.append(row)
    recycle_rows = read_ndjson("recycle_bin.ndjson") + moved; retained = []
    for row in recycle_rows:
        try: expired = parsed(str(row.get("recycledAt", ""))) < purge_before
        except Exception: expired = False
        if not expired: retained.append(row)
    if moved: write_ndjson("anomalies.ndjson", kept)
    write_ndjson("recycle_bin.ndjson", retained)
    return {"archived": len(moved), "purged": len(recycle_rows) - len(retained)}
