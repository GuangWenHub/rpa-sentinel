import unittest

from rpa_monitor.rules import apply_handling_status, annotate_attention, filter_anomaly_view, normalize_job, retry_guards, task_name
from rpa_monitor.yingdao import status_cn
from rpa_monitor.codex_ai import _failure_message, _replace_env_value


class RuleTests(unittest.TestCase):
    def test_loop_attention_starts_at_five(self):
        rows = [{"jobUuid": str(i), "taskName": "10min_demo", "robotUuid": "r1", "status": "error", "triggerTime": f"2026-09-15T08:{i:02d}:00"} for i in range(1, 6)]
        result = annotate_attention(rows)
        self.assertFalse(result[3]["needsAttention"])
        self.assertTrue(result[4]["needsAttention"])
        self.assertFalse(result[4]["aiEligible"])

    def test_success_breaks_loop_streak(self):
        rows = [{"taskName": "20min_demo", "robotUuid": "r", "status": s, "triggerTime": str(i)} for i, s in enumerate(["error"] * 4 + ["success", "error"])]
        self.assertEqual(annotate_attention(rows)[-1]["consecutiveErrorCount"], 1)

    def test_status_mapping(self):
        self.assertEqual(status_cn("running"), "运行中")
        self.assertEqual(status_cn("finished"), "完成")
        self.assertEqual(status_cn("stopped"), "已停止")
        self.assertEqual(status_cn("error"), "异常")

    def test_recent_success_guard(self):
        job = {"jobUuid": "bad", "taskName": "普通任务", "status": "error"}
        settings = {"max_auto_retries": 2, "require_recent_success": True, "block_if_same_task_running": False, "block_high_risk_keywords": False, "block_if_evidence_insufficient": False, "retry_blacklist": []}
        reasons = retry_guards(job, settings, [], {"allow_retry": True, "evidence_sufficient": True}, 0)
        self.assertIn("近期同名任务没有成功记录", reasons)

    def test_attention_keeps_resolved_rows(self):
        rows = [
            {"needsAttention": True, "resolved": True, "job": {"jobUuid": "resolved"}},
            {"needsAttention": True, "resolved": False, "job": {"jobUuid": "open"}},
            {"needsAttention": False, "resolved": False, "job": {"jobUuid": "filtered"}},
        ]
        result = filter_anomaly_view(rows, "attention")
        self.assertEqual([x["job"]["jobUuid"] for x in result], ["resolved", "open"])

    def test_handling_status_keeps_record_and_distinguishes_ignored(self):
        rows = [{"resolved": False, "job": {"jobUuid": "one"}}]
        self.assertTrue(apply_handling_status(rows, "one", "ignored"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["handlingStatus"], "ignored")
        self.assertFalse(rows[0]["resolved"])
        self.assertTrue(apply_handling_status(rows, "one", "resolved"))
        self.assertTrue(rows[0]["resolved"])

    def test_advanced_api_job_uses_robot_name(self):
        job = normalize_job({
            "jobUuid": "59300e0f-0e65-4203-8bb9-ac589a2fd3e2",
            "robotName": "每两周_天猫部_自制短视频数据拉取",
        })
        self.assertEqual(task_name(job), "每两周_天猫部_自制短视频数据拉取")
        self.assertTrue(job["isAdvancedTask"])
        self.assertEqual(job["taskTypeCn"], "高级任务")

    def test_normal_job_keeps_task_name(self):
        job = normalize_job({"taskName": "10min_普通任务", "robotName": "应用名称"})
        self.assertEqual(task_name(job), "10min_普通任务")
        self.assertFalse(job["isAdvancedTask"])
        self.assertEqual(job["taskTypeCn"], "普通任务")

    def test_codex_desktop_session_error_is_actionable(self):
        message = _failure_message("thread/resume failed: no rollout found")
        self.assertIn("Codex exec 会话", message)

    def test_replace_codex_session_preserves_other_env_values(self):
        content = "CODEX_MODEL=test-model\nCODEX_SESSION_ID=old\n"
        updated = _replace_env_value(content, "CODEX_SESSION_ID", "new")
        self.assertIn("CODEX_MODEL=test-model", updated)
        self.assertIn("CODEX_SESSION_ID=new", updated)
        self.assertNotIn("CODEX_SESSION_ID=old", updated)


if __name__ == "__main__": unittest.main()
