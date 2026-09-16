from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtCore import QObject, QPoint, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QColor, QCursor, QFont, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)
from rpa_monitor.rules import task_name as normalized_task_name


APP_STYLE = """
* { font-family: "Microsoft YaHei UI"; font-size: 13px; }
QMainWindow, QWidget#Root { background: #f4f6fa; color: #182230; }
QFrame#Sidebar { background: #111827; border: none; }
QLabel#Brand { color: white; font-size: 19px; font-weight: 700; }
QLabel#BrandSub { color: #94a3b8; font-size: 11px; }
QPushButton#NavButton { color: #cbd5e1; text-align: left; padding: 11px 14px; border: 0; border-radius: 8px; }
QPushButton#NavButton:hover { background: #1f2937; color: white; }
QPushButton#NavButton:checked { background: #2563eb; color: white; font-weight: 600; }
QLabel#SidebarHint { color: #94a3b8; padding: 8px; }
QLabel#PageTitle { font-size: 24px; font-weight: 700; color: #111827; }
QLabel#PageSub { color: #64748b; }
QFrame#Card, QFrame#Panel { background: white; border: 1px solid #e6eaf0; border-radius: 12px; }
QLabel#CardTitle { color: #64748b; font-size: 12px; }
QLabel#CardValue { color: #111827; font-size: 24px; font-weight: 700; }
QPushButton { background: white; border: 1px solid #d9dee8; border-radius: 7px; padding: 7px 12px; }
QPushButton:hover { border-color: #94a3b8; background: #f8fafc; }
QPushButton:disabled { color: #94a3b8; background: #f1f5f9; }
QPushButton#Primary { color: white; background: #2563eb; border-color: #2563eb; font-weight: 600; }
QPushButton#Primary:hover { background: #1d4ed8; }
QPushButton#Danger { color: #b42318; background: #fff7f6; border-color: #fecaca; }
QPushButton#RowAction { padding: 4px 8px; font-size: 11px; min-width: 52px; }
QPushButton#ResolveAction:checked { color: white; background: #16a34a; border-color: #16a34a; }
QPushButton#IgnoreAction:checked { color: #92400e; background: #fef3c7; border-color: #f59e0b; }
QPushButton#ViewButton { border: 0; border-radius: 7px; color: #64748b; padding: 7px 11px; }
QPushButton#ViewButton:checked { background: #e8f0ff; color: #1d4ed8; font-weight: 600; }
QLineEdit, QComboBox, QSpinBox, QTextEdit { background: white; border: 1px solid #d9dee8; border-radius: 7px; padding: 7px; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus { border-color: #3b82f6; }
QTableWidget { background: white; border: 0; gridline-color: #edf0f4; selection-background-color: #e8f0ff; selection-color: #182230; }
QHeaderView::section { background: #f8fafc; color: #64748b; border: 0; border-bottom: 1px solid #e5e9f0; padding: 9px; font-weight: 600; }
QTableWidget::item { padding: 8px; border-bottom: 1px solid #f0f2f5; }
QScrollBar:vertical { width: 10px; background: transparent; }
QScrollBar::handle:vertical { background: #cbd5e1; min-height: 24px; border-radius: 5px; }
QCheckBox { spacing: 8px; }
QToolTip { background: #111827; color: white; border: 0; padding: 6px; }
"""


def text(value) -> str:
    return "" if value is None else str(value)


def display_row(record: dict, wrapped: bool) -> dict:
    job = record.get("job", {}) if wrapped else record
    analysis = record.get("analysis") or {} if wrapped else {}
    ai_state = {
        "failed_waiting": "待人工判断",
        "done": "已分析",
        "skipped_loop": "循环任务不分析",
        "filtered": "未达关注条件",
        "pending": "待分析",
    }.get(text(record.get("aiState")), text(record.get("aiState")))
    handling = text(record.get("handlingStatus")) if wrapped else ""
    if wrapped and not handling:
        handling = "resolved" if record.get("resolved") else "pending"
    return {
        "job_uuid": text(job.get("jobUuid")),
        "trigger_time": text(job.get("triggerTime")),
        "task_name": normalized_task_name(job),
        "robot": text(job.get("robotClientName")),
        "status": text(job.get("statusCn") or job.get("status")),
        "consecutive": text(job.get("consecutiveErrorCount")),
        "ai_state": ai_state,
        "summary": text(analysis.get("summary") or job.get("remark") or job.get("message")),
        "resolved": bool(record.get("resolved")) if wrapped else False,
        "handling": handling,
        "screenshot": text(job.get("screenshotPath")),
        "analysis": analysis,
        "wrapped": wrapped,
        "raw": record,
    }


class FilterHeader(QHeaderView):
    filter_requested = Signal(int, QPoint)

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.active_columns: set[int] = set()
        self.setSectionsClickable(True)

    def set_filter_active(self, column: int, active: bool):
        if active:
            self.active_columns.add(column)
        else:
            self.active_columns.discard(column)
        self.viewport().update()

    def paintSection(self, painter: QPainter, rect, logical_index: int):
        super().paintSection(painter, rect, logical_index)
        painter.save()
        painter.setPen(QColor("#2563eb" if logical_index in self.active_columns else "#94a3b8"))
        painter.drawText(rect.adjusted(0, 0, -7, -3), Qt.AlignRight | Qt.AlignBottom, "▾")
        painter.restore()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            column = self.logicalIndexAt(event.position().toPoint())
            if column >= 0:
                self.filter_requested.emit(column, self.viewport().mapToGlobal(event.position().toPoint()))
                return
        super().mousePressEvent(event)


class CliWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, arguments: list[str]):
        super().__init__()
        self.arguments = arguments

    def run(self) -> None:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(SRC) + (os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
        environment["PYTHONUTF8"] = "1"
        environment["PYTHONIOENCODING"] = "utf-8"
        try:
            result = subprocess.run(
                [sys.executable, "-m", "rpa_monitor.cli", *self.arguments],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            lines = [line for line in result.stdout.splitlines() if line.strip()]
            if not lines:
                raise RuntimeError("后台程序没有返回数据。" + result.stderr.strip())
            payload = json.loads(lines[-1])
            if result.returncode or (isinstance(payload, dict) and payload.get("ok") is False):
                raise RuntimeError(text(payload.get("error")) or result.stderr.strip() or "后台操作失败")
            self.finished.emit(payload)
        except Exception as exc:
            self.failed.emit(str(exc))


class CommandHandler(QObject):
    def __init__(self, on_success, on_error, parent=None):
        super().__init__(parent)
        self.on_success = on_success
        self.on_error = on_error

    @Slot(object)
    def succeeded(self, payload):
        self.on_success(payload)

    @Slot(str)
    def failed(self, message: str):
        self.on_error(message)


class ZoomImageDialog(QDialog):
    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("异常截图 · 滚轮缩放")
        self.resize(1100, 760)
        layout = QVBoxLayout(self)
        self.view = QGraphicsView()
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.scene = QGraphicsScene(self)
        self.view.setScene(self.scene)
        pixmap = QPixmap(path)
        self.scene.addItem(QGraphicsPixmapItem(pixmap))
        self.view.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
        original_wheel = self.view.wheelEvent

        def wheel(event):
            factor = 1.18 if event.angleDelta().y() > 0 else 0.85
            self.view.scale(factor, factor)

        self.view.wheelEvent = wheel
        layout.addWidget(self.view)


class RecycleDialog(QDialog):
    restore_requested = Signal(str)

    def __init__(self, rows: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("异常回收站")
        self.resize(920, 540)
        layout = QVBoxLayout(self)
        title = QLabel(f"回收站 · {len(rows)} 条记录")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["触发时间", "任务名称", "机器人", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for raw in rows:
            row = display_row(raw, True)
            index = self.table.rowCount()
            self.table.insertRow(index)
            for column, value in enumerate((row["trigger_time"], row["task_name"], row["robot"], row["status"])):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.UserRole, row["job_uuid"])
                self.table.setItem(index, column, item)
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        actions.addStretch()
        close = QPushButton("关闭")
        restore = QPushButton("恢复选中记录")
        restore.setObjectName("Primary")
        close.clicked.connect(self.reject)
        restore.clicked.connect(self.restore)
        actions.addWidget(close)
        actions.addWidget(restore)
        layout.addLayout(actions)

    def restore(self):
        index = self.table.currentRow()
        if index < 0:
            QMessageBox.information(self, "恢复记录", "请先选择一条记录。")
            return
        self.restore_requested.emit(text(self.table.item(index, 0).data(Qt.UserRole)))


class MainWindow(QMainWindow):
    def __init__(self, start_hidden: bool = False):
        super().__init__()
        self.setWindowTitle("RPA Sentinel · 异常哨兵")
        self.resize(1480, 900)
        self.setMinimumSize(1120, 700)
        self.start_hidden = start_hidden
        self.exit_requested = False
        self.current_view = "attention"
        self.rows: list[dict] = []
        self.column_filters: dict[int, str] = {}
        self.settings: dict = {}
        self.next_due: datetime | None = None
        self.workers: set[tuple[QThread, CliWorker, CommandHandler]] = set()
        self.busy_count = 0
        self.exit_timer = QTimer(self)
        self.exit_timer.setInterval(100)
        self.exit_timer.timeout.connect(self._finish_exit_when_idle)
        self._build_ui()
        self._build_tray()
        self._bind()
        self.scheduler = QTimer(self)
        self.scheduler.setInterval(30_000)
        self.scheduler.timeout.connect(self.on_schedule_tick)
        self.scheduler.start()
        self.run_cli(["settings-get"], self.settings_loaded, "读取设置")

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(224)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 24, 18, 18)
        brand = QLabel("RPA Sentinel")
        brand.setObjectName("Brand")
        sub = QLabel("异常发现 · 分析 · 处置")
        sub.setObjectName("BrandSub")
        side.addWidget(brand)
        side.addWidget(sub)
        side.addSpacing(28)
        self.monitor_nav = self._nav_button("运行看板")
        self.settings_nav = self._nav_button("巡检设置")
        self.monitor_nav.setChecked(True)
        side.addWidget(self.monitor_nav)
        side.addWidget(self.settings_nav)
        side.addStretch()
        self.side_status = QLabel("● 正在初始化")
        self.side_status.setObjectName("SidebarHint")
        self.side_status.setWordWrap(True)
        side.addWidget(self.side_status)
        self.pause_button = QPushButton("暂停巡检")
        side.addWidget(self.pause_button)
        shell.addWidget(sidebar)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_monitor_page())
        self.pages.addWidget(self._build_settings_page())
        shell.addWidget(self.pages, 1)

    def _nav_button(self, label: str) -> QPushButton:
        button = QPushButton(label)
        button.setObjectName("NavButton")
        button.setCheckable(True)
        button.setAutoExclusive(True)
        return button

    def _build_monitor_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(14)
        heading = QHBoxLayout()
        head_text = QVBoxLayout()
        title = QLabel("运行看板")
        title.setObjectName("PageTitle")
        self.subtitle = QLabel("正在读取本地运行数据…")
        self.subtitle.setObjectName("PageSub")
        head_text.addWidget(title)
        head_text.addWidget(self.subtitle)
        heading.addLayout(head_text)
        heading.addStretch()
        self.next_run = QLabel("下次巡检  --")
        self.next_run.setStyleSheet("color:#2563eb;font-weight:600;padding:8px 12px;background:#e8f0ff;border-radius:8px")
        self.scan_button = QPushButton("立即巡检")
        self.scan_button.setObjectName("Primary")
        heading.addWidget(self.next_run)
        heading.addWidget(self.scan_button)
        layout.addLayout(heading)

        cards = QHBoxLayout()
        self.attention_value = self._stat_card(cards, "需关注异常", "0", "#dc2626")
        self.error_value = self._stat_card(cards, "全部异常", "0", "#d97706")
        self.running_value = self._stat_card(cards, "正在运行", "0", "#2563eb")
        self.total_value = self._stat_card(cards, "当前视图", "0", "#0f766e")
        layout.addLayout(cards)

        toolbar = QHBoxLayout()
        self.view_buttons: dict[str, QPushButton] = {}
        for key, label in (("attention", "需关注"), ("errors", "全部异常"), ("all", "全部记录")):
            button = QPushButton(label)
            button.setObjectName("ViewButton")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setChecked(key == "attention")
            self.view_buttons[key] = button
            toolbar.addWidget(button)
        toolbar.addSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索任务、机器人或错误摘要")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(260)
        toolbar.addWidget(self.search, 1)
        self.columns_button = QToolButton()
        self.columns_button.setText("显示列")
        self.columns_button.setPopupMode(QToolButton.InstantPopup)
        toolbar.addWidget(self.columns_button)
        self.recycle_button = QPushButton("回收站")
        toolbar.addWidget(self.recycle_button)
        self.refresh_button = QPushButton("刷新")
        toolbar.addWidget(self.refresh_button)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Vertical)
        table_panel = QFrame()
        table_panel.setObjectName("Panel")
        table_layout = QVBoxLayout(table_panel)
        table_layout.setContentsMargins(1, 1, 1, 1)
        self.table = QTableWidget(0, 8)
        self.headers = ["触发时间", "任务名称", "执行机器人", "运行状态", "连续异常", "AI 状态", "错误摘要", "处理方式"]
        self.table.setHorizontalHeaderLabels(self.headers)
        self.filter_header = FilterHeader(self.table)
        self.table.setHorizontalHeader(self.filter_header)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Fixed)
        self.table.setColumnWidth(7, 150)
        table_layout.addWidget(self.table)
        splitter.addWidget(table_panel)
        splitter.addWidget(self._build_detail_panel())
        splitter.setSizes([540, 230])
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)
        self._build_columns_menu()
        return page

    def _stat_card(self, parent: QHBoxLayout, title: str, initial: str, color: str) -> QLabel:
        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        label = QLabel(title)
        label.setObjectName("CardTitle")
        value = QLabel(initial)
        value.setObjectName("CardValue")
        value.setStyleSheet(f"color:{color}")
        card_layout.addWidget(label)
        card_layout.addWidget(value)
        parent.addWidget(card)
        return value

    def _build_detail_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        text_side = QVBoxLayout()
        title = QLabel("异常详情")
        title.setStyleSheet("font-size:17px;font-weight:700")
        text_side.addWidget(title)
        self.detail_meta = QLabel("选择一条记录查看详情")
        self.detail_meta.setObjectName("PageSub")
        self.detail_meta.setWordWrap(True)
        text_side.addWidget(self.detail_meta)
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setPlaceholderText("错误摘要和 AI 分析会显示在这里")
        text_side.addWidget(self.detail_text, 1)
        layout.addLayout(text_side, 1)
        self.screenshot = QLabel("本次记录无截图")
        self.screenshot.setAlignment(Qt.AlignCenter)
        self.screenshot.setFixedWidth(360)
        self.screenshot.setMinimumHeight(150)
        self.screenshot.setCursor(Qt.PointingHandCursor)
        self.screenshot.setStyleSheet("background:#f1f5f9;color:#94a3b8;border-radius:8px")
        self.screenshot.setScaledContents(False)
        layout.addWidget(self.screenshot)
        return panel

    def _build_settings_page(self) -> QWidget:
        wrapper = QWidget()
        outer = QVBoxLayout(wrapper)
        outer.setContentsMargins(26, 22, 26, 22)
        title = QLabel("巡检设置")
        title.setObjectName("PageTitle")
        sub = QLabel("设置保存后立即重新计算下一次巡检时间")
        sub.setObjectName("PageSub")
        outer.addWidget(title)
        outer.addWidget(sub)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content.setMaximumWidth(920)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 16, 0, 16)
        content_layout.setSpacing(14)

        schedule = self._settings_card("巡检计划")
        form: QFormLayout = schedule.layout().itemAt(1).layout()
        time_row = QHBoxLayout()
        self.start_time = QLineEdit()
        self.start_time.setPlaceholderText("08:00")
        self.end_time = QLineEdit()
        self.end_time.setPlaceholderText("17:30")
        self.frequency = QSpinBox()
        self.frequency.setRange(1, 1440)
        self.frequency.setSuffix(" 分钟")
        time_row.addWidget(QLabel("开始"))
        time_row.addWidget(self.start_time)
        time_row.addWidget(QLabel("结束"))
        time_row.addWidget(self.end_time)
        time_row.addWidget(QLabel("频率"))
        time_row.addWidget(self.frequency)
        form.addRow("执行时段", time_row)
        self.roster = QCheckBox("按飞书排班日历判断当天是否执行（每天最多读取一次）")
        form.addRow("排班开关", self.roster)
        content_layout.addWidget(schedule)

        safety = self._settings_card("AI 分析与重试安全")
        safety_form: QFormLayout = safety.layout().itemAt(1).layout()
        self.auto_retry = QCheckBox("允许 AI 判断后自动立即重试（默认关闭）")
        self.max_retries = QSpinBox()
        self.max_retries.setRange(1, 3)
        self.retry_timeout = QSpinBox()
        self.retry_timeout.setRange(1, 1440)
        self.retry_timeout.setSuffix(" 分钟")
        safety_form.addRow("自动重试", self.auto_retry)
        safety_form.addRow("最大次数", self.max_retries)
        safety_form.addRow("超时时间", self.retry_timeout)
        self.guard_running = QCheckBox("同名任务正在运行时禁止自动重试")
        self.guard_risk = QCheckBox("命中高风险关键词时禁止自动重试")
        self.guard_evidence = QCheckBox("AI 证据不足时禁止自动重试")
        self.guard_success = QCheckBox("近期同名任务无成功记录时禁止自动重试")
        guard_box = QVBoxLayout()
        for control in (self.guard_running, self.guard_risk, self.guard_evidence, self.guard_success):
            guard_box.addWidget(control)
        safety_form.addRow("安全条件", guard_box)
        self.blacklist = QTextEdit()
        self.blacklist.setFixedHeight(80)
        self.blacklist.setPlaceholderText("每行一个任务名")
        self.risk_words = QTextEdit()
        self.risk_words.setFixedHeight(80)
        safety_form.addRow("任务黑名单", self.blacklist)
        safety_form.addRow("高风险关键词", self.risk_words)
        codex_row = QHBoxLayout()
        self.codex_session_button = QPushButton("初始化/更换分析会话")
        self.codex_session_hint = QLabel("使用本机 Codex CLI 的专用 exec 会话")
        self.codex_session_hint.setObjectName("PageSub")
        codex_row.addWidget(self.codex_session_button)
        codex_row.addWidget(self.codex_session_hint)
        codex_row.addStretch()
        safety_form.addRow("Codex 会话", codex_row)
        content_layout.addWidget(safety)

        notice = QLabel("排期重试目前仅保留框架：不会连接 PostgreSQL，不会读取甘特图，也不会启用排期队列。")
        notice.setWordWrap(True)
        notice.setStyleSheet("background:#fff7e6;color:#92400e;border:1px solid #fde6b3;border-radius:8px;padding:12px")
        content_layout.addWidget(notice)
        self.save_button = QPushButton("保存设置")
        self.save_button.setObjectName("Primary")
        self.save_button.setFixedWidth(120)
        content_layout.addWidget(self.save_button, 0, Qt.AlignRight)
        content_layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        return wrapper

    def _settings_card(self, title: str) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        heading = QLabel(title)
        heading.setStyleSheet("font-size:17px;font-weight:700")
        layout.addWidget(heading)
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addLayout(form)
        return card

    def _build_columns_menu(self):
        menu = QMenu(self)
        self.column_actions: list[QAction] = []
        for index, header in enumerate(self.headers):
            action = QAction(header, self, checkable=True, checked=True)
            action.toggled.connect(lambda visible, column=index: self.set_column_visible(column, visible))
            menu.addAction(action)
            self.column_actions.append(action)
        self.columns_button.setMenu(menu)

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self)
        icon = self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon)
        self.setWindowIcon(icon)
        self.tray.setIcon(icon)
        self.tray.setToolTip("RPA Sentinel · 异常哨兵")
        menu = QMenu()
        show = menu.addAction("打开控制台")
        pause = menu.addAction("暂停/继续巡检")
        menu.addSeparator()
        exit_action = menu.addAction("退出程序")
        show.triggered.connect(self.restore_window)
        pause.triggered.connect(self.toggle_pause)
        exit_action.triggered.connect(self.exit_application)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.restore_window() if reason == QSystemTrayIcon.DoubleClick else None)
        self.tray.show()

    def _bind(self):
        self.monitor_nav.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        self.settings_nav.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        for key, button in self.view_buttons.items():
            button.clicked.connect(lambda checked=False, view=key: self.change_view(view))
        self.search.textChanged.connect(self.render_rows)
        self.refresh_button.clicked.connect(self.refresh_records)
        self.scan_button.clicked.connect(self.manual_scan)
        self.recycle_button.clicked.connect(self.open_recycle)
        self.table.itemSelectionChanged.connect(self.show_selected)
        self.table.cellDoubleClicked.connect(self.cell_double_clicked)
        self.table.customContextMenuRequested.connect(self.table_context_menu)
        self.filter_header.filter_requested.connect(self.open_column_filter)
        self.screenshot.mousePressEvent = lambda event: self.open_screenshot() if event.button() == Qt.LeftButton else None
        self.save_button.clicked.connect(self.save_settings)
        self.codex_session_button.clicked.connect(self.initialize_codex_session)
        self.pause_button.clicked.connect(self.toggle_pause)
        QShortcut(QKeySequence.Refresh, self, activated=self.refresh_records)

    def run_cli(self, arguments: list[str], on_success, label: str, on_error=None):
        self.busy_count += 1
        self.side_status.setText(f"● {label}中…")
        thread = QThread(self)
        worker = CliWorker(arguments)
        worker.moveToThread(thread)

        def finish(payload):
            on_success(payload)

        def fail(message):
            if on_error:
                on_error(message)
            else:
                QMessageBox.warning(self, f"{label}失败", message)

        handler = CommandHandler(finish, fail, self)
        pair = (thread, worker, handler)
        self.workers.add(pair)
        thread.started.connect(worker.run)

        worker.finished.connect(handler.succeeded)
        worker.failed.connect(handler.failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(handler.deleteLater)
        thread.finished.connect(lambda: self._worker_done(pair))
        thread.start()

    def _worker_done(self, pair):
        self.workers.discard(pair)
        self.busy_count = max(0, self.busy_count - 1)
        if not self.busy_count:
            self.update_side_status()
        if self.exit_requested and not self.workers:
            self._finish_exit_when_idle()

    def settings_loaded(self, settings: dict):
        self.settings = settings
        self.start_time.setText(text(settings.get("start_time", "08:00")))
        self.end_time.setText(text(settings.get("end_time", "17:30")))
        self.frequency.setValue(int(settings.get("frequency_minutes", 10)))
        self.roster.setChecked(bool(settings.get("read_roster", True)))
        self.auto_retry.setChecked(bool(settings.get("ai_auto_retry", False)))
        self.max_retries.setValue(int(settings.get("max_auto_retries", 2)))
        self.retry_timeout.setValue(int(settings.get("retry_timeout_minutes", 45)))
        self.guard_running.setChecked(bool(settings.get("block_if_same_task_running", True)))
        self.guard_risk.setChecked(bool(settings.get("block_high_risk_keywords", True)))
        self.guard_evidence.setChecked(bool(settings.get("block_if_evidence_insufficient", True)))
        self.guard_success.setChecked(bool(settings.get("require_recent_success", True)))
        self.blacklist.setPlainText("\n".join(settings.get("retry_blacklist", [])))
        self.risk_words.setPlainText("\n".join(settings.get("retry_block_keywords", [])))
        hidden = set(settings.get("hidden_columns", []))
        for index, action in enumerate(self.column_actions):
            action.setChecked(self.headers[index] not in hidden)
        self.reset_next_due()
        self.update_side_status()
        self.refresh_records()

    def update_side_status(self):
        paused = bool(self.settings.get("paused"))
        self.side_status.setText("● 巡检已暂停" if paused else "● 后台巡检运行中")
        self.pause_button.setText("继续巡检" if paused else "暂停巡检")

    def reset_next_due(self):
        if self.settings.get("paused"):
            self.next_due = None
            self.next_run.setText("下次巡检  已暂停")
            return
        now = datetime.now()
        try:
            start_h, start_m = map(int, self.settings.get("start_time", "08:00").split(":"))
            end_h, end_m = map(int, self.settings.get("end_time", "17:30").split(":"))
            start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
            end = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
            frequency = max(1, int(self.settings.get("frequency_minutes", 10)))
            if now < start:
                due = start
            elif now > end:
                due = start + timedelta(days=1)
            else:
                steps = int((now - start).total_seconds() // 60 // frequency) + 1
                due = start + timedelta(minutes=steps * frequency)
                if due > end:
                    due = start + timedelta(days=1)
            self.next_due = due
            self.next_run.setText("下次巡检  " + due.strftime("%m-%d %H:%M"))
        except Exception:
            self.next_due = None
            self.next_run.setText("下次巡检  设置无效")

    def refresh_records(self):
        self.run_cli(["data", "--view", self.current_view], self.records_loaded, "刷新数据", self.data_error)

    def data_error(self, message: str):
        self.subtitle.setText("读取失败：" + message)

    def records_loaded(self, records):
        wrapped = self.current_view != "all"
        self.rows = [display_row(row, wrapped) for row in records]
        self.render_rows()
        self.subtitle.setText(f"已读取 {len(self.rows)} 条记录 · 窗口关闭后仍在后台巡检")
        self.update_cards()

    def render_rows(self):
        if not hasattr(self, "table"):
            return
        term = self.search.text().strip().lower()
        filtered = [
            row for row in self.rows
            if (not term or term in (row["task_name"] + " " + row["robot"] + " " + row["summary"]).lower())
            and all(self._column_value(row, column) == value for column, value in self.column_filters.items())
        ]
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        values = ("trigger_time", "task_name", "robot", "status", "consecutive", "ai_state", "summary")
        for row in filtered:
            index = self.table.rowCount()
            self.table.insertRow(index)
            for column, key in enumerate(values):
                item = QTableWidgetItem(text(row[key]))
                if column == 0:
                    item.setData(Qt.UserRole, row)
                if row["handling"] in ("resolved", "ignored"):
                    item.setForeground(QColor("#94a3b8"))
                    item.setBackground(QColor("#f1f5f9" if row["handling"] == "resolved" else "#fffbeb"))
                elif key == "status" and row[key] == "异常":
                    item.setForeground(QColor("#dc2626"))
                    item.setFont(QFont(item.font().family(), item.font().pointSize(), QFont.DemiBold))
                self.table.setItem(index, column, item)
            handling_item = QTableWidgetItem(self._handling_label(row["handling"]))
            self.table.setItem(index, 7, handling_item)
            if row["wrapped"]:
                self.table.setCellWidget(index, 7, self._handling_buttons(row))
        self.total_value.setText(str(len(filtered)))
        self.detail_meta.setText("选择一条记录查看详情")
        self.detail_text.clear()
        self.set_screenshot("")

    def _handling_label(self, value: str) -> str:
        return {"resolved": "已解决", "ignored": "无需处理", "pending": "待处理", "": "—"}.get(value, value)

    def _column_value(self, row: dict, column: int) -> str:
        if column == 0:
            return row["trigger_time"][:10] or "未记录"
        keys = {1: "task_name", 2: "robot", 3: "status", 4: "consecutive", 5: "ai_state", 6: "summary"}
        if column == 7:
            return self._handling_label(row["handling"])
        return text(row.get(keys.get(column, ""))) or "未记录"

    def _handling_buttons(self, row: dict) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(3, 2, 3, 2)
        layout.setSpacing(4)
        resolved = QPushButton("已解决")
        ignored = QPushButton("无需处理")
        resolved.setObjectName("ResolveAction")
        ignored.setObjectName("IgnoreAction")
        for button in (resolved, ignored):
            button.setCheckable(True)
            button.setFixedHeight(28)
        resolved.setChecked(row["handling"] == "resolved")
        ignored.setChecked(row["handling"] == "ignored")
        resolved.clicked.connect(
            lambda checked, job=row["job_uuid"]: self.set_handling_status(job, "resolved" if checked else "pending")
        )
        ignored.clicked.connect(
            lambda checked, job=row["job_uuid"]: self.set_handling_status(job, "ignored" if checked else "pending")
        )
        layout.addWidget(resolved)
        layout.addWidget(ignored)
        return container

    def open_column_filter(self, column: int, position: QPoint):
        values = sorted({self._column_value(row, column) for row in self.rows}, reverse=column == 0)
        menu = QMenu(self)
        all_action = menu.addAction("全部")
        all_action.setCheckable(True)
        all_action.setChecked(column not in self.column_filters)
        all_action.triggered.connect(lambda: self.apply_column_filter(column, None))
        menu.addSeparator()
        current = self.column_filters.get(column)
        for value in values:
            label = value if len(value) <= 48 else value[:45] + "…"
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(value == current)
            action.triggered.connect(lambda checked=False, selected=value: self.apply_column_filter(column, selected))
        menu.exec(position)

    def apply_column_filter(self, column: int, value: str | None):
        if value is None:
            self.column_filters.pop(column, None)
        else:
            self.column_filters[column] = value
        self.filter_header.set_filter_active(column, value is not None)
        self.render_rows()

    def update_cards(self):
        attention = sum(1 for row in self.rows if row["wrapped"] and row["handling"] == "pending" and row["raw"].get("needsAttention"))
        errors = sum(1 for row in self.rows if row["status"] == "异常")
        running = sum(1 for row in self.rows if row["status"] == "运行中")
        self.attention_value.setText(str(attention if self.current_view != "all" else "—"))
        self.error_value.setText(str(errors))
        self.running_value.setText(str(running))

    def selected_row(self) -> dict | None:
        index = self.table.currentRow()
        if index < 0 or not self.table.item(index, 0):
            return None
        return self.table.item(index, 0).data(Qt.UserRole)

    def show_selected(self):
        row = self.selected_row()
        if not row:
            return
        self.detail_meta.setText(
            f"{row['task_name']}\n{row['trigger_time']} · {row['robot'] or '未记录执行机器人'} · {row['status']}"
        )
        analysis_text = json.dumps(row["analysis"], ensure_ascii=False, indent=2) if row["analysis"] else "暂无 AI 分析"
        summary = row["summary"] or "本次记录没有错误摘要"
        self.detail_text.setPlainText(f"错误摘要\n{summary}\n\nAI 分析\n{analysis_text}")
        self.set_screenshot(row["screenshot"])

    def set_screenshot(self, path: str):
        self.current_screenshot = path if path and Path(path).exists() else ""
        if not self.current_screenshot:
            self.screenshot.setPixmap(QPixmap())
            self.screenshot.setText("本次记录无截图")
            return
        pixmap = QPixmap(self.current_screenshot)
        self.screenshot.setText("")
        self.screenshot.setPixmap(pixmap.scaled(360, 210, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def change_view(self, view: str):
        self.current_view = view
        self.refresh_records()

    def manual_scan(self):
        self.scan_button.setEnabled(False)

        def complete(result):
            self.scan_button.setEnabled(True)
            self.subtitle.setText(f"巡检完成：读取 {result.get('fetched', 0)} 条，需关注 {result.get('attention', 0)} 条")
            self.refresh_records()
            self.reset_next_due()

        self.run_cli(["scan", "--force"], complete, "立即巡检", lambda message: self.scan_failed(message))

    def scan_failed(self, message: str):
        self.scan_button.setEnabled(True)
        QMessageBox.critical(self, "巡检失败", message)

    def analyze_selected(self):
        row = self.selected_row()
        if not row:
            return
        self.run_cli(["analyze", "--job", row["job_uuid"]], lambda _: self.refresh_records(), "AI 分析")

    def retry_selected(self):
        row = self.selected_row()
        if not row:
            return
        answer = QMessageBox.warning(
            self,
            "重试风险确认",
            f"立即重试会直接调用影刀重试接口。若机器已有任务，可能导致等待或超时。\n\n确认重试：{row['task_name']}？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        def complete(result):
            QMessageBox.information(self, "重试已提交", f"重试请求已受理，第 {result.get('attempt', 1)} 次。")

        self.run_cli(["retry", "--job", row["job_uuid"]], complete, "手动重试")

    def set_handling_status(self, job_uuid: str, value: str):
        self.run_cli(["handle", "--job", job_uuid, "--value", value], lambda _: self.refresh_records(), "更新处理方式")

    def cell_double_clicked(self, row_index: int, column: int):
        if column != 1:
            return
        item = self.table.item(row_index, column)
        if not item:
            return
        QApplication.clipboard().setText(item.text())
        QToolTip.showText(QCursor.pos(), "已写入剪贴板", self.table, self.table.visualItemRect(item), 1800)
        self.subtitle.setText(f"已复制任务名：{item.text()}")

    def table_context_menu(self, point: QPoint):
        if self.table.indexAt(point).row() < 0:
            return
        self.table.selectRow(self.table.indexAt(point).row())
        row = self.selected_row()
        if not row or not row["wrapped"]:
            return
        menu = QMenu(self)
        analyze = menu.addAction("执行 AI 分析")
        retry = menu.addAction("手动重试")
        menu.addSeparator()
        recycle = menu.addAction("放入回收站")
        chosen = menu.exec(self.table.viewport().mapToGlobal(point))
        if chosen == analyze:
            self.analyze_selected()
        elif chosen == retry:
            self.retry_selected()
        elif chosen == recycle:
            self.recycle_selected()

    def recycle_selected(self):
        row = self.selected_row()
        if not row:
            return
        if QMessageBox.question(self, "放入回收站", f"将“{row['task_name']}”放入回收站？") != QMessageBox.Yes:
            return
        self.run_cli(["recycle", "--job", row["job_uuid"]], lambda _: self.refresh_records(), "放入回收站")

    def open_recycle(self):
        self.run_cli(["data", "--view", "recycle"], self.show_recycle_dialog, "读取回收站")

    def show_recycle_dialog(self, rows):
        dialog = RecycleDialog(rows, self)

        def restore(job_uuid: str):
            self.run_cli(["restore", "--job", job_uuid], lambda _: self.recycle_restored(dialog), "恢复记录")

        dialog.restore_requested.connect(restore)
        dialog.exec()

    def recycle_restored(self, dialog: QDialog):
        dialog.accept()
        self.refresh_records()

    def open_screenshot(self):
        if self.current_screenshot:
            ZoomImageDialog(self.current_screenshot, self).exec()

    def save_settings(self):
        for field, label in ((self.start_time.text(), "开始时间"), (self.end_time.text(), "结束时间")):
            try:
                datetime.strptime(field, "%H:%M")
            except ValueError:
                QMessageBox.warning(self, "设置错误", f"{label}必须使用 HH:mm 格式。")
                return
        updated = dict(self.settings)
        updated.update(
            {
                "start_time": self.start_time.text(),
                "end_time": self.end_time.text(),
                "frequency_minutes": self.frequency.value(),
                "read_roster": self.roster.isChecked(),
                "ai_auto_retry": self.auto_retry.isChecked(),
                "max_auto_retries": self.max_retries.value(),
                "retry_timeout_minutes": self.retry_timeout.value(),
                "block_if_same_task_running": self.guard_running.isChecked(),
                "block_high_risk_keywords": self.guard_risk.isChecked(),
                "block_if_evidence_insufficient": self.guard_evidence.isChecked(),
                "require_recent_success": self.guard_success.isChecked(),
                "retry_blacklist": [x.strip() for x in self.blacklist.toPlainText().splitlines() if x.strip()],
                "retry_block_keywords": [x.strip() for x in self.risk_words.toPlainText().splitlines() if x.strip()],
            }
        )
        payload = json.dumps(updated, ensure_ascii=False, separators=(",", ":"))

        def complete(settings):
            self.settings = settings
            self.reset_next_due()
            self.update_side_status()
            QMessageBox.information(self, "设置", "设置已保存，新计划立即生效。")

        self.run_cli(["settings-save", payload], complete, "保存设置")

    def initialize_codex_session(self):
        answer = QMessageBox.question(
            self,
            "初始化 Codex 分析会话",
            "将创建一个新的本地 Codex 只读分析会话，并替换当前 CODEX_SESSION_ID。\n"
            "模型和其他配置不会改变。是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.codex_session_button.setEnabled(False)
        self.codex_session_hint.setText("正在连接本机 Codex 并验证结构化输出…")

        def complete(result):
            self.codex_session_button.setEnabled(True)
            self.codex_session_hint.setText(f"专用分析会话已就绪 · {result.get('model', '')}")
            QMessageBox.information(self, "Codex 会话", "专用分析会话初始化成功。")

        def failed(message):
            self.codex_session_button.setEnabled(True)
            self.codex_session_hint.setText("初始化失败，请检查 Codex 登录和网络状态")
            QMessageBox.warning(self, "Codex 会话初始化失败", message)

        self.run_cli(["ai-session-init"], complete, "初始化 Codex 会话", failed)

    def set_column_visible(self, column: int, visible: bool):
        self.table.setColumnHidden(column, not visible)
        if not self.settings:
            return
        self.settings["hidden_columns"] = [
            self.headers[index] for index, action in enumerate(self.column_actions) if not action.isChecked()
        ]

    def toggle_pause(self):
        if not self.settings:
            return
        updated = dict(self.settings)
        updated["paused"] = not bool(updated.get("paused"))
        payload = json.dumps(updated, ensure_ascii=False, separators=(",", ":"))

        def complete(settings):
            self.settings = settings
            self.update_side_status()
            self.reset_next_due()

        self.run_cli(["settings-save", payload], complete, "更新巡检状态")

    def on_schedule_tick(self):
        if self.busy_count or self.settings.get("paused") or not self.next_due or datetime.now() < self.next_due:
            return

        def complete(result):
            notifications = result.get("notifications") or []
            if notifications:
                self.tray.showMessage("RPA 异常更新", text(notifications[0].get("message")), QSystemTrayIcon.Warning, 5000)
            self.refresh_records()
            self.reset_next_due()

        self.run_cli(["scan"], complete, "后台巡检", lambda message: self.background_scan_error(message))

    def background_scan_error(self, message: str):
        self.subtitle.setText("巡检失败：" + message)
        self.reset_next_due()

    def restore_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def exit_application(self):
        self.exit_requested = True
        self.tray.hide()
        self.hide()
        if self.workers:
            self.side_status.setText("● 正在结束后台读取…")
            self.exit_timer.start()
        else:
            QApplication.quit()

    def _finish_exit_when_idle(self):
        if self.workers:
            return
        self.exit_timer.stop()
        QApplication.quit()

    def closeEvent(self, event):
        if self.exit_requested:
            event.accept()
            return
        event.ignore()
        self.hide()
        self.tray.showMessage("RPA Sentinel · 异常哨兵", "控制台已缩到后台，巡检仍会继续运行。", QSystemTrayIcon.Information, 2500)

    def showEvent(self, event):
        super().showEvent(event)
        if self.start_hidden:
            self.start_hidden = False
            QTimer.singleShot(0, self.hide)


def main() -> int:
    if not (ROOT / ".env").exists():
        initializer = ROOT / "app" / "初始化配置.ps1"
        if initializer.exists():
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(initializer), "-ProjectDir", str(ROOT)],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
    app = QApplication(sys.argv)
    app.setApplicationName("RPA Sentinel")
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(APP_STYLE)
    window = MainWindow(start_hidden="--start-hidden" in sys.argv)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
