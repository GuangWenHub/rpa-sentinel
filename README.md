# RPA Sentinel（RPA 异常哨兵）

RPA Sentinel 是影刀公有云运行记录巡检与异常闭环控制台。当前提供新版 PySide6 图形界面和原 WPF 回退界面，在后台按 GUI 设置的时间段和频率运行。

## 当前能力

- 默认 08:00—17:30、每 10 分钟巡检一次，保存设置后立即重新计算下次触发时间。
- 可选择按飞书排班日历判断当天是否执行；排班每天只读取一次。关闭该选项则每天按设置执行。
- 首次扫描完整读取从昨天 17:30 到当前时间的记录，后续每次只读取最近 50 条。
- 支持需关注异常、全部异常、全部运行记录，以及运行中、等待调度、完成、停止中、已停止、异常状态筛选。
- 循环任务 `10min_`、`20min_` 连续异常达到 5 次才进入需关注视图，并且不调用 Codex。
- 非循环需关注异常可通过本机 Codex 会话分析；截图存在时一并提交。
- 支持已解决、回收站、恢复、手动立即重试和默认关闭的 AI 自动重试。
- 窗口关闭后缩到系统托盘继续运行，只有“暂停巡检”会暂停。

## 启动

新版界面使用仓库内独立环境，首次使用先安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

然后双击 `启动新版巡检控制台.vbs`，或运行：

```powershell
.\.venv\Scripts\pythonw.exe app/qt_console.py
```

原 WPF 版本仍可双击 `启动巡检控制台.vbs` 启动，作为回退入口。首次运行前，在本目录 `.env` 中补齐必要配置。

### 初始化 Codex 异常分析会话

AI 分析使用本机 Codex CLI，不调用 OpenAI API。`CODEX_SESSION_ID` 必须是专用的非交互 `codex exec` 会话，不能填写 Codex 桌面或 IDE 会话 ID。首次使用或出现“不是可续接的 Codex exec 会话”时，在仓库根目录执行一次：

```powershell
$env:PYTHONPATH = (Resolve-Path '.\src').Path
python -m rpa_monitor.cli ai-session-init
```

初始化只会创建一个只读分析会话，并替换 `.env` 中的 `CODEX_SESSION_ID`；不会修改模型或其他配置。后续所有异常分析固定续接该会话。

启动时如果 `.env` 不存在，程序会先调用 `app/初始化配置.ps1`，把同名 Windows 用户环境变量复制到 `.env`。此操作不会修改或删除 Windows 环境变量；未能自动取得的值仍需手工填写。

## 目录结构

| 路径 | 作用 |
|---|---|
| `app/` | PySide6 新版界面、WPF 回退界面、配置初始化与启动逻辑 |
| `src/rpa_monitor/` | 巡检、影刀 API、规则、AI、重试、排班、存储模块 |
| `config/` | AI 输出结构等非敏感配置 |
| `tests/` | 不触发真实重试的本地测试 |
| `data/` | 本地运行记录、状态、截图、回收站；不提交 Git |
| `AGENTS.md` | 后续 Agent 的强制开发、测试和安全规则 |
| `.env` | 本机敏感配置，不提交 Git |
| `.env.example` | 无真实值的配置模板 |

本目录顶层原有的 Python、PowerShell 与旧运行数据仅为回退保留；新版入口只使用 `app/`、`src/`、`config/` 和 `data/`。旧运行数据也已加入 Git 排除规则。

## 模块说明

- `config.py`：路径、`.env`、GUI 设置和默认值。
- `yingdao.py`：影刀令牌、运行记录、详情、截图及重试接口。
- `rules.py`：循环任务、连续异常及自动重试安全条件。
- `monitor.py`：每轮巡检的编排与状态落盘。
- `codex_ai.py`：续接当前本地 Codex 会话进行只读分析；额度失败时 30 分钟后重试分析。
- `retry.py`：手动/自动立即重试与跨新 jobUuid 的重试链计数。
- `roster.py`：飞书排班日历每日缓存与授权异常处理。
- `storage.py`：JSON、NDJSON、回收站的原子读写。
- `scheduling.py`：排期重试预留框架；当前不读 PostgreSQL、不启用甘特图排期。
- `cli.py`：WPF 与后台模块之间的稳定命令入口。

## 安全边界

- 所有敏感值只从本仓库根目录 `.env` 读取。初始化只复制 Windows 用户环境变量，不修改或删除原环境变量。
- 自动重试默认关闭；循环任务永不自动重试。AI 分析失败、额度不足或证据不足时转人工判断。
- 手动重试必须显示风险提示并由操作者确认；本地测试不会调用真实重试接口。
- 飞书“影刀消息”暂不读取。排期重试目前只有代码框架。
