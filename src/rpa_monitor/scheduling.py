"""排期重试预留框架。

后续实现边界：
1. GanttSource 从 PyTaskGantt 后端 API 或 PostgreSQL JSON 读取计划。
2. 按 robotClientName 匹配机器，解析任务开始/结束时间。
3. 结合预计运行时长和缓冲时间寻找空闲窗口。
4. 到点前再查询影刀实际运行状态；冲突时顺延。
5. 数据库连接只来自项目 .env。

当前版本只支持立即重试，不读取甘特图、不连接 PostgreSQL。
"""
from __future__ import annotations


class RetryScheduler:
    enabled = False

    def plan(self, *_args, **_kwargs):
        raise NotImplementedError("排期重试尚未启用；当前版本仅支持立即重试")
