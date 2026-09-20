import unittest
from datetime import datetime

from app.qt_console import calculate_next_due, display_row, parse_local_time


class QtConsoleLogicTests(unittest.TestCase):
    def test_next_due_advances_to_next_frequency_slot(self):
        settings = {"start_time": "08:00", "end_time": "17:30", "frequency_minutes": 10}
        self.assertEqual(
            calculate_next_due(datetime(2026, 9, 20, 14, 40, 1), settings),
            datetime(2026, 9, 20, 14, 50),
        )

    def test_next_due_rolls_to_tomorrow_after_window(self):
        settings = {"start_time": "08:00", "end_time": "17:30", "frequency_minutes": 10}
        self.assertEqual(
            calculate_next_due(datetime(2026, 9, 20, 17, 31), settings),
            datetime(2026, 9, 21, 8, 0),
        )

    def test_ai_column_uses_analysis_summary(self):
        row = display_row(
            {
                "job": {"jobUuid": "one", "taskName": "任务"},
                "aiState": "done",
                "analysis": {"summary": "这是完整的 AI 分析结论"},
            },
            True,
        )
        self.assertEqual(row["ai_result"], "这是完整的 AI 分析结论")

    def test_last_scan_timestamp_is_converted_to_local_naive_time(self):
        parsed = parse_local_time("2026-09-20T14:40:14+08:00")
        self.assertIsNotNone(parsed)
        self.assertIsNone(parsed.tzinfo)


if __name__ == "__main__":
    unittest.main()
