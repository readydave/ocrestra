from __future__ import annotations

import importlib.metadata
import json
import multiprocessing as mp
import os
import queue
import re
import shlex
import shutil
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psutil
from PySide6.QtCore import QEvent, QSettings, QStandardPaths, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QDragEnterEvent, QDropEvent, QIcon, QPainter, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QInputDialog,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .config import (
    APP_NAME,
    DEFAULT_WORKERS,
    LOG_ROOT,
    MAX_DISCOVERED_PDFS,
    MAX_INPUT_FILE_BYTES,
    MAX_QUEUE_ITEMS,
    MAX_SCAN_DEPTH,
    MAX_WORKERS,
    ORG_NAME,
    SETTINGS_APP,
    TEMP_ROOT,
)
from .job_runner import run_ocr_job
from .models import TaskItem
from .themes import apply_theme

TABLE_COL_INPUT = 0
TABLE_COL_STATUS = 1
TABLE_COL_PROGRESS = 2
TABLE_COL_RESULT = 3
TABLE_COL_LOG = 4
TABLE_COL_ACTION = 5

FILE_MANAGER_OPTIONS_LINUX = [
    ("auto", "Auto (Recommended)", None),
    ("system", "System Default", None),
    ("dolphin", "Dolphin", ["dolphin", "{path}"]),
    ("krusader", "Krusader", ["krusader", "{path}"]),
    ("nautilus", "Nautilus", ["nautilus", "{path}"]),
    ("thunar", "Thunar", ["thunar", "{path}"]),
    ("nemo", "Nemo", ["nemo", "{path}"]),
    ("pcmanfm", "PCManFM", ["pcmanfm", "{path}"]),
    ("xdg-open", "xdg-open", ["xdg-open", "{path}"]),
]
FILE_MANAGER_OPTIONS_WINDOWS = [
    ("auto", "Auto (Recommended)", None),
    ("system", "System Default", None),
    ("explorer", "Explorer", ["explorer", "{path}"]),
]
FILE_MANAGER_OPTIONS_MACOS = [
    ("auto", "Auto (Recommended)", None),
    ("system", "System Default", None),
    ("finder", "Finder", ["open", "{path}"]),
]

MAX_STATE_FILE_BYTES = 2 * 1024 * 1024
MAX_RESTORE_PATHS = 5000
MAX_CUSTOM_FILE_MANAGER_CMD_LEN = 512


def _resolve_app_icon_path() -> Path | None:
    assets_dir = Path(__file__).resolve().parent.parent / "assets"
    candidates = []
    if sys.platform.startswith("win"):
        candidates = [assets_dir / "ocrestra.ico", assets_dir / "ocrestra.png"]
    else:
        candidates = [assets_dir / "ocrestra.png", assets_dir / "ocrestra.ico"]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _set_windows_app_user_model_id() -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        app_id = f"{ORG_NAME}.{APP_NAME}".replace(" ", "")
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        return


def _linux_desktop_entry_available(app_id: str) -> bool:
    if not sys.platform.startswith("linux"):
        return False
    candidates = []
    for base in (
        Path.home() / ".local" / "share" / "applications",
        Path("/usr/local/share/applications"),
        Path("/usr/share/applications"),
    ):
        candidates.append(base / f"{app_id}.desktop")
    return any(path.exists() and path.is_file() for path in candidates)


def _format_bytes(size: int) -> str:
    if size <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def _safe_file_part(value: str) -> str:
    filtered = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)
    return filtered.strip("_") or "job"


class DropZone(QFrame):
    paths_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("DropZone")
        self.setProperty("hover", False)
        layout = QVBoxLayout(self)
        label = QLabel("Drop PDFs or folders here")
        sub = QLabel("Tip: You can add folders recursively and process in parallel")
        label.setAlignment(Qt.AlignCenter)
        sub.setAlignment(Qt.AlignCenter)
        sub.setObjectName("DropZoneSub")
        layout.addStretch()
        layout.addWidget(label)
        layout.addWidget(sub)
        layout.addStretch()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            self._set_hover(True)
            event.acceptProposedAction()
            return
        self._set_hover(False)

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._set_hover(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        paths: list[str] = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                paths.append(url.toLocalFile())
        if paths:
            self.paths_dropped.emit(paths)
        self._set_hover(False)
        event.acceptProposedAction()

    def _set_hover(self, is_hover: bool) -> None:
        if self.property("hover") == is_hover:
            return
        self.setProperty("hover", is_hover)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class ArrowComboBox(QComboBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        popup_view = self.view()
        if popup_view is not None:
            popup_view.setObjectName("ComboPopupView")

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        color = self.palette().color(QPalette.ButtonText)
        if not self.isEnabled():
            color = self.palette().color(QPalette.Disabled, QPalette.ButtonText)
        painter.setPen(color)
        arrow_rect = self.rect().adjusted(self.width() - 24, 0, -6, 0)
        painter.drawText(arrow_rect, Qt.AlignCenter, "▼")


class CollapsibleSection(QFrame):
    def __init__(self, title: str, expanded: bool = False) -> None:
        super().__init__()
        self.setObjectName("CollapsibleSection")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.toggle = QToolButton(self)
        self.toggle.setObjectName("SectionToggle")
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(expanded)
        self.toggle.setText(title)
        self.toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.toggle.toggled.connect(self._on_toggled)
        root.addWidget(self.toggle)

        self.content = QWidget(self)
        self.content.setVisible(expanded)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(12, 0, 0, 0)
        self.content_layout.setSpacing(10)
        root.addWidget(self.content)

    def _on_toggled(self, checked: bool) -> None:
        self.toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        self.content.setVisible(checked)


class QueueEmptyStateOverlay(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("QueueEmptyState")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addStretch()

        self.card = QFrame(self)
        self.card.setObjectName("EmptyStateCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(8)

        self.title = QLabel("Your queue is empty", self.card)
        self.title.setObjectName("EmptyStateTitle")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setWordWrap(True)
        self.body = QLabel("Add PDF files or drag folders into the drop zone to begin OCR.", self.card)
        self.body.setObjectName("EmptyStateBody")
        self.body.setAlignment(Qt.AlignCenter)
        self.body.setWordWrap(True)

        card_layout.addWidget(self.title)
        card_layout.addWidget(self.body)

        layout.addWidget(self.card, alignment=Qt.AlignCenter)
        layout.addStretch()
        self._update_for_size()

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _update_for_size(self) -> None:
        available_width = max(260, self.width() - 56)
        card_width = int(self._clamp(available_width * 0.84, 320, 820))
        self.card.setFixedWidth(card_width)
        self.body.setMaximumWidth(card_width - 52)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_for_size()


class MainWindow(QMainWindow):
    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self.app = app
        self.system_palette = app.palette()
        self.system_style = app.style().objectName()
        self.settings = QSettings(ORG_NAME, SETTINGS_APP)
        self.last_dir = self.settings.value("last_dir", str(Path.home()), type=str)
        self.theme = self.settings.value("theme", "system", type=str)
        self.path_display_mode = self.settings.value("path_display_mode", "elided", type=str)
        self.folder_scan_recursive = self.settings.value("folder_scan_recursive", True, type=bool)
        self.file_manager_choice = self.settings.value("file_manager_choice", "auto", type=str)
        self.file_manager_custom_cmd = self.settings.value("file_manager_custom_cmd", "", type=str).strip()
        self.custom_manager_warned_this_session = False
        self.priority_mode = self.settings.value("priority_mode", "normal", type=str)
        self.use_gpu_acceleration = self.settings.value("use_gpu_acceleration", False, type=bool)
        self.optimize_for_size = self.settings.value("optimize_for_size", False, type=bool)
        valid_choices = {manager_id for manager_id, _label, _cmd in self._file_manager_options_for_platform()}
        valid_choices.add("custom")
        if self.file_manager_choice not in valid_choices:
            self.file_manager_choice = "auto"
        if self.file_manager_custom_cmd:
            cmd_ok, _cmd_err = self._validate_custom_file_manager_template(self.file_manager_custom_cmd)
            if not cmd_ok:
                self.file_manager_custom_cmd = ""
        if self.file_manager_choice == "custom" and not self.file_manager_custom_cmd:
            self.file_manager_choice = "auto"

        self.tasks: dict[str, TaskItem] = {}
        self.path_to_task: dict[str, str] = {}
        self.log_entries: list[tuple[str | None, str, str]] = []
        self.active_run_token = 0
        self.total_batch = 0
        self.finished_batch = 0
        self.batch_running = False
        self.current_worker_limit = DEFAULT_WORKERS
        self.current_force_ocr = False
        self.current_use_gpu = False
        self.current_optimize_for_size = False
        self.batch_log_dir: Path | None = None

        self.app_proc = psutil.Process(os.getpid())
        self.app_proc.cpu_percent(None)

        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)

        self.setWindowTitle(APP_NAME)
        self.resize(1360, 860)
        self._build_ui()
        self._build_menus()
        self._apply_saved_theme()
        self._update_parallel_mode_controls()
        self._update_parallel_hint()
        self._update_batch_progress()
        self._update_metrics_labels()
        self._refresh_file_manager_actions()
        self._restore_queue_state_prompt()
        self._check_runtime_dependencies()

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(200)
        self.poll_timer.timeout.connect(self._poll_workers)
        self.poll_timer.start()

        self.metrics_timer = QTimer(self)
        self.metrics_timer.setInterval(1000)
        self.metrics_timer.timeout.connect(self._update_metrics_labels)
        self.metrics_timer.start()

        self.state_timer = QTimer(self)
        self.state_timer.setInterval(8000)
        self.state_timer.timeout.connect(self._save_queue_state)
        self.state_timer.start()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        title_wrap = QVBoxLayout()
        title = QLabel("OCRestra")
        title.setObjectName("Title")
        subtitle = QLabel("Process-level OCR jobs with live logs, metrics, and cancel control")
        subtitle.setObjectName("Subtitle")
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)
        header_row.addLayout(title_wrap)
        header_row.addStretch()

        self.cancel_selected_button = QPushButton("Cancel Selected")
        self.cancel_all_button = QPushButton("Cancel All")
        self.clear_button = QPushButton("Clear List")
        self.start_button = QPushButton("Start OCR")
        self.start_button.setObjectName("StartButton")
        self.start_button.setDefault(True)
        self.start_button.setAutoDefault(True)
        self.exit_button = QPushButton("Exit")
        self.exit_button.setObjectName("DangerButton")
        for button in (
            self.cancel_selected_button,
            self.cancel_all_button,
            self.clear_button,
            self.start_button,
            self.exit_button,
        ):
            button.setMinimumWidth(118)

        header_row.addWidget(self.cancel_selected_button)
        header_row.addWidget(self.cancel_all_button)
        header_row.addWidget(self.clear_button)
        header_row.addSpacing(10)
        header_row.addWidget(self.start_button)
        header_row.addWidget(self.exit_button)
        layout.addLayout(header_row)

        self.main_splitter = QSplitter(Qt.Horizontal, root)
        self.main_splitter.setObjectName("MainSplitter")
        layout.addWidget(self.main_splitter, 1)

        config_scroll = QScrollArea(self.main_splitter)
        config_scroll.setWidgetResizable(True)
        config_scroll.setFrameShape(QFrame.NoFrame)
        config_scroll.setObjectName("ConfigScrollArea")
        config_scroll.setMinimumWidth(320)

        config_panel = QWidget(config_scroll)
        config_layout = QVBoxLayout(config_panel)
        config_layout.setContentsMargins(0, 0, 0, 0)
        config_layout.setSpacing(12)

        self.drop_zone = DropZone()
        self.drop_zone.paths_dropped.connect(self.add_paths)
        config_layout.addWidget(self.drop_zone)

        source_actions = QHBoxLayout()
        self.add_pdf_button = QPushButton("Add PDFs")
        self.add_folder_button = QPushButton("Add Folder")
        source_actions.addWidget(self.add_pdf_button)
        source_actions.addWidget(self.add_folder_button)
        source_actions.addStretch()
        config_layout.addLayout(source_actions)

        self.ocr_mode = ArrowComboBox()
        self.ocr_mode.addItem("Smart OCR (Skip text)", "smart")
        self.ocr_mode.addItem("Force OCR (All pages)", "force")
        saved_ocr_mode = self.settings.value("ocr_mode", "smart", type=str)
        self._set_combo_data(self.ocr_mode, saved_ocr_mode)

        self.path_display_combo = ArrowComboBox()
        self.path_display_combo.addItem("Full path", "full")
        self.path_display_combo.addItem("Elided path", "elided")
        self.path_display_combo.addItem("Filename only", "name")
        self._set_combo_data(self.path_display_combo, self.path_display_mode)

        self.parallel_mode = ArrowComboBox()
        self.parallel_mode.addItem("Auto (Recommended)", "auto")
        self.parallel_mode.addItem("Low (4)", "4")
        self.parallel_mode.addItem("Balanced (8)", "8")
        self.parallel_mode.addItem("High (16)", "16")
        self.parallel_mode.addItem("Turbo (24)", "24")
        self.parallel_mode.addItem("Max (32)", "32")
        self.parallel_mode.addItem("Custom", "custom")
        saved_mode = self.settings.value("parallel_mode", "auto", type=str)
        self._set_combo_data(self.parallel_mode, saved_mode)

        self.custom_workers = QSpinBox()
        self.custom_workers.setRange(1, MAX_WORKERS)
        self.custom_workers.setValue(self.settings.value("custom_workers", DEFAULT_WORKERS, type=int))

        self.priority_combo = ArrowComboBox()
        self.priority_combo.addItem("Normal Priority", "normal")
        self.priority_combo.addItem("Low Impact", "low")
        self.priority_combo.addItem("Background (Low + I/O)", "background")
        self._set_combo_data(self.priority_combo, self.priority_mode)

        self.advanced_section = CollapsibleSection("Advanced", expanded=False)
        advanced_form = QFormLayout()
        advanced_form.setContentsMargins(0, 0, 0, 0)
        advanced_form.setSpacing(10)
        advanced_form.addRow("OCR mode", self.ocr_mode)
        advanced_form.addRow("Path display", self.path_display_combo)
        advanced_form.addRow("Priority", self.priority_combo)

        parallel_wrap = QWidget()
        parallel_layout = QHBoxLayout(parallel_wrap)
        parallel_layout.setContentsMargins(0, 0, 0, 0)
        parallel_layout.setSpacing(8)
        parallel_layout.addWidget(self.parallel_mode, 1)
        parallel_layout.addWidget(self.custom_workers)
        advanced_form.addRow("Parallel files", parallel_wrap)

        gpu_help_text = (
            "Use NVIDIA CUDA through the ocrmypdf-easyocr plugin.\n"
            "Best for image-heavy scans and large batches.\n"
            "Requires: ocrmypdf-easyocr, torch CUDA runtime, NVIDIA driver."
        )
        self.gpu_checkbox = QCheckBox("Enable GPU Acceleration (NVIDIA CUDA)")
        self.gpu_checkbox.setChecked(self.use_gpu_acceleration)
        advanced_form.addRow("", self._build_option_row(self.gpu_checkbox, gpu_help_text))

        compression_help_text = (
            "Applies balanced compression to reduce output size.\n"
            "Good for email/sharing/cloud archives.\n"
            "Avoid for legal/archival scans or very small/faint text."
        )
        self.optimize_size_checkbox = QCheckBox("Optimize for Smaller Output")
        self.optimize_size_checkbox.setChecked(self.optimize_for_size)
        advanced_form.addRow("", self._build_option_row(self.optimize_size_checkbox, compression_help_text))
        self.advanced_section.content_layout.addLayout(advanced_form)
        config_layout.addWidget(self.advanced_section)

        self.parallel_hint = QLabel("")
        self.parallel_hint.setObjectName("ParallelHint")
        self.parallel_hint.setWordWrap(True)
        config_layout.addWidget(self.parallel_hint)

        stats_visible = self.settings.value("show_stats", True, type=bool)
        self.stats_frame = QFrame()
        self.stats_frame.setObjectName("StatsFrame")
        stats_layout = QVBoxLayout(self.stats_frame)
        stats_layout.setContentsMargins(10, 10, 10, 10)
        stats_layout.setSpacing(8)

        stats_title = QLabel("Runtime Stats")
        stats_title.setObjectName("MetricsTitle")
        stats_layout.addWidget(stats_title)

        metrics_grid = QGridLayout()
        metrics_grid.setHorizontalSpacing(12)
        metrics_grid.setVerticalSpacing(6)

        def _metric_key(text: str) -> QLabel:
            label = QLabel(text)
            label.setObjectName("MetricKey")
            return label

        self.metrics_app_cpu = QLabel("0.0%")
        self.metrics_app_ram = QLabel("0 B")
        self.metrics_sys_cpu = QLabel("0.0%")
        self.metrics_sys_ram = QLabel("0.0%")
        self.metrics_gpu = QLabel("N/A")
        self.metrics_gpu_vram = QLabel("N/A")
        self.metrics_workers = QLabel("0 active / 0 queued")
        self.metrics_cpu_health = QLabel("Green")
        self.metrics_ram_health = QLabel("Green")

        metric_values = (
            self.metrics_app_cpu,
            self.metrics_app_ram,
            self.metrics_sys_cpu,
            self.metrics_sys_ram,
            self.metrics_gpu,
            self.metrics_gpu_vram,
            self.metrics_workers,
            self.metrics_cpu_health,
            self.metrics_ram_health,
        )
        for label in metric_values:
            label.setObjectName("MetricValue")

        metrics_grid.addWidget(_metric_key("App CPU"), 0, 0)
        metrics_grid.addWidget(self.metrics_app_cpu, 0, 1)
        metrics_grid.addWidget(_metric_key("App RAM"), 0, 2)
        metrics_grid.addWidget(self.metrics_app_ram, 0, 3)

        metrics_grid.addWidget(_metric_key("System CPU"), 1, 0)
        metrics_grid.addWidget(self.metrics_sys_cpu, 1, 1)
        metrics_grid.addWidget(_metric_key("System RAM"), 1, 2)
        metrics_grid.addWidget(self.metrics_sys_ram, 1, 3)

        metrics_grid.addWidget(_metric_key("GPU"), 2, 0)
        metrics_grid.addWidget(self.metrics_gpu, 2, 1)
        metrics_grid.addWidget(_metric_key("VRAM"), 2, 2)
        metrics_grid.addWidget(self.metrics_gpu_vram, 2, 3)

        metrics_grid.addWidget(_metric_key("Workers"), 3, 0)
        metrics_grid.addWidget(self.metrics_workers, 3, 1, 1, 3)

        metrics_grid.addWidget(_metric_key("CPU Health"), 4, 0)
        metrics_grid.addWidget(self.metrics_cpu_health, 4, 1)
        metrics_grid.addWidget(_metric_key("RAM Health"), 4, 2)
        metrics_grid.addWidget(self.metrics_ram_health, 4, 3)

        stats_layout.addLayout(metrics_grid)
        config_layout.addWidget(self.stats_frame)
        config_layout.addStretch()

        config_scroll.setWidget(config_panel)
        self.main_splitter.addWidget(config_scroll)

        right_pane = QWidget()
        right_pane.setMinimumWidth(620)
        right_layout = QVBoxLayout(right_pane)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        self.queue_log_splitter = QSplitter(Qt.Vertical, right_pane)
        self.queue_log_splitter.setObjectName("QueueLogSplitter")
        right_layout.addWidget(self.queue_log_splitter, 1)

        queue_panel = QWidget()
        queue_layout = QVBoxLayout(queue_panel)
        queue_layout.setContentsMargins(0, 0, 0, 0)
        queue_layout.setSpacing(10)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Input PDF", "Status", "Progress", "Result", "Log", "Action"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(TABLE_COL_INPUT, QHeaderView.Interactive)
        header.setSectionResizeMode(TABLE_COL_STATUS, QHeaderView.Fixed)
        header.setSectionResizeMode(TABLE_COL_PROGRESS, QHeaderView.Fixed)
        header.setSectionResizeMode(TABLE_COL_RESULT, QHeaderView.Interactive)
        header.setSectionResizeMode(TABLE_COL_LOG, QHeaderView.Fixed)
        header.setSectionResizeMode(TABLE_COL_ACTION, QHeaderView.Fixed)
        header.setStretchLastSection(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideMiddle)
        self._auto_adjust_table_columns()
        queue_layout.addWidget(self.table, 1)

        self.empty_state_overlay = QueueEmptyStateOverlay(self.table.viewport())
        self.table_viewport = self.table.viewport()
        self.table_viewport.installEventFilter(self)

        progress_row = QHBoxLayout()
        self.batch_label = QLabel("Batch progress: 0/0")
        self.batch_progress = QProgressBar()
        self.batch_progress.setRange(0, 100)
        self.batch_progress.setValue(0)
        progress_row.addWidget(self.batch_label)
        progress_row.addWidget(self.batch_progress, 1)
        queue_layout.addLayout(progress_row)

        self.show_stats_toggle = QCheckBox("Show Stats")
        self.show_stats_toggle.setChecked(stats_visible)
        toggle_row = QHBoxLayout()
        toggle_row.addStretch()
        toggle_row.addWidget(self.show_stats_toggle)
        queue_layout.addLayout(toggle_row)

        self.queue_log_splitter.addWidget(queue_panel)

        log_panel = QWidget()
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(10)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Live process logs stream here...")
        log_controls = QHBoxLayout()
        self.log_filter_combo = ArrowComboBox()
        self.log_filter_combo.addItem("All logs", "all")
        self.log_filter_combo.addItem("Selected file only", "selected")
        self.log_level_combo = ArrowComboBox()
        self.log_level_combo.addItem("Any level", "all")
        self.log_level_combo.addItem("Warnings only", "warning")
        self.log_level_combo.addItem("Errors only", "error")
        log_controls.addWidget(QLabel("Log view"))
        log_controls.addWidget(self.log_filter_combo)
        log_controls.addWidget(QLabel("Level"))
        log_controls.addWidget(self.log_level_combo)
        log_controls.addStretch()
        log_layout.addLayout(log_controls)
        log_layout.addWidget(self.log_view, 1)
        self.queue_log_splitter.addWidget(log_panel)
        self.main_splitter.addWidget(right_pane)

        self.add_pdf_button.clicked.connect(self._pick_pdfs)
        self.add_folder_button.clicked.connect(self._pick_folder)
        self.start_button.clicked.connect(self.start_batch)
        self.exit_button.clicked.connect(self.close)
        self.cancel_selected_button.clicked.connect(self.cancel_selected)
        self.cancel_all_button.clicked.connect(self.cancel_all)
        self.clear_button.clicked.connect(self.clear_tasks)
        self.parallel_mode.currentIndexChanged.connect(self._update_parallel_mode_controls)
        self.parallel_mode.currentIndexChanged.connect(self._update_parallel_hint)
        self.custom_workers.valueChanged.connect(self._update_parallel_hint)
        self.ocr_mode.currentIndexChanged.connect(self._update_parallel_hint)
        self.gpu_checkbox.toggled.connect(self._on_gpu_toggle_changed)
        self.optimize_size_checkbox.toggled.connect(self._on_optimize_size_changed)
        self.priority_combo.currentIndexChanged.connect(self._on_priority_changed)
        self.path_display_combo.currentIndexChanged.connect(self._on_path_display_changed)
        self.log_filter_combo.currentIndexChanged.connect(self._refresh_log_view)
        self.log_level_combo.currentIndexChanged.connect(self._refresh_log_view)
        self.show_stats_toggle.toggled.connect(self._set_stats_visible)
        self.table.itemSelectionChanged.connect(self._refresh_log_view)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        self.main_splitter.splitterMoved.connect(lambda _pos, _index: self._sync_empty_state_overlay())
        self.queue_log_splitter.splitterMoved.connect(lambda _pos, _index: self._sync_empty_state_overlay())
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(10)
        self.queue_log_splitter.setChildrenCollapsible(False)
        self.queue_log_splitter.setHandleWidth(10)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([480, 880])
        self.queue_log_splitter.setStretchFactor(0, 2)
        self.queue_log_splitter.setStretchFactor(1, 1)
        self.queue_log_splitter.setSizes([520, 280])
        self._update_splitter_orientation()
        self._set_stats_visible(stats_visible)
        self._sync_empty_state_overlay()

    def _build_menus(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("File")
        tools_menu = menu.addMenu("Tools")
        help_menu = menu.addMenu("Help")

        add_pdf_action = QAction("Add PDFs", self)
        add_folder_action = QAction("Add Folder", self)
        start_action = QAction("Start OCR", self)
        cancel_all_action = QAction("Cancel All", self)
        exit_action = QAction("Exit", self)
        add_pdf_action.triggered.connect(self._pick_pdfs)
        add_folder_action.triggered.connect(self._pick_folder)
        start_action.triggered.connect(self.start_batch)
        cancel_all_action.triggered.connect(self.cancel_all)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(add_pdf_action)
        file_menu.addAction(add_folder_action)
        file_menu.addSeparator()
        file_menu.addAction(start_action)
        file_menu.addAction(cancel_all_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        theme_menu = QMenu("Themes", self)
        tools_menu.addMenu(theme_menu)
        self.theme_group = QActionGroup(self)
        self.theme_group.setExclusive(True)
        self.theme_actions: dict[str, QAction] = {}
        for key, label in [("system", "System (Default)"), ("dark", "Dark"), ("light", "Light")]:
            action = QAction(label, self, checkable=True)
            action.triggered.connect(lambda checked, name=key: self.set_theme(name))
            self.theme_group.addAction(action)
            theme_menu.addAction(action)
            self.theme_actions[key] = action

        open_logs_action = QAction("Open Log Folder", self)
        open_logs_action.triggered.connect(self.open_log_folder)
        tools_menu.addAction(open_logs_action)
        reset_defaults_action = QAction("Reset to Defaults", self)
        reset_defaults_action.triggered.connect(self._reset_to_defaults)
        tools_menu.addAction(reset_defaults_action)

        file_manager_menu = QMenu("File Manager", self)
        tools_menu.addMenu(file_manager_menu)
        file_manager_menu.aboutToShow.connect(self._refresh_file_manager_actions)
        self.file_manager_action_group = QActionGroup(self)
        self.file_manager_action_group.setExclusive(True)
        self.file_manager_actions: dict[str, QAction] = {}
        for manager_id, label, _ in self._file_manager_options_for_platform():
            action = QAction(label, self, checkable=True)
            action.triggered.connect(
                lambda checked, mid=manager_id: self._set_file_manager_choice(mid)
            )
            self.file_manager_action_group.addAction(action)
            file_manager_menu.addAction(action)
            self.file_manager_actions[manager_id] = action
        custom_action = QAction("Custom Command", self, checkable=True)
        custom_action.triggered.connect(lambda checked: self._set_file_manager_choice("custom"))
        self.file_manager_action_group.addAction(custom_action)
        file_manager_menu.addAction(custom_action)
        self.file_manager_actions["custom"] = custom_action
        file_manager_menu.addSeparator()
        self.set_custom_manager_action = QAction("Set Custom Command...", self)
        self.set_custom_manager_action.triggered.connect(self._set_custom_file_manager_command)
        file_manager_menu.addAction(self.set_custom_manager_action)

        usage_action = QAction("Usage", self)
        about_action = QAction("About", self)
        usage_action.triggered.connect(self.show_usage)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(usage_action)
        help_menu.addAction(about_action)

    def _apply_saved_theme(self) -> None:
        if self.theme not in {"system", "dark", "light"}:
            self.theme = "system"
        self.set_theme(self.theme, save=False)

    def set_theme(self, theme: str, save: bool = True) -> None:
        self.theme = theme
        apply_theme(self.app, theme, self.system_palette, self.system_style)
        action = self.theme_actions.get(theme)
        if action is not None:
            action.setChecked(True)
        if save:
            self.settings.setValue("theme", theme)

    def _reset_to_defaults(self) -> None:
        answer = QMessageBox.question(
            self,
            "Reset to Defaults",
            "Reset appearance and processing preferences to defaults?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        defaults = {
            "theme": "system",
            "parallel_mode": "auto",
            "custom_workers": DEFAULT_WORKERS,
            "ocr_mode": "smart",
            "use_gpu_acceleration": False,
            "optimize_for_size": False,
            "folder_scan_recursive": True,
            "priority_mode": "normal",
            "path_display_mode": "elided",
            "show_stats": True,
            "file_manager_choice": "auto",
            "file_manager_custom_cmd": "",
        }
        for key, value in defaults.items():
            self.settings.setValue(key, value)

        self._set_combo_data(self.ocr_mode, "smart")
        self._set_combo_data(self.parallel_mode, "auto")
        self.custom_workers.setValue(DEFAULT_WORKERS)
        self._set_combo_data(self.priority_combo, "normal")
        self._set_combo_data(self.path_display_combo, "elided")
        self.gpu_checkbox.setChecked(False)
        self.optimize_size_checkbox.setChecked(False)
        self.use_gpu_acceleration = False
        self.optimize_for_size = False
        self.folder_scan_recursive = True
        self.priority_mode = "normal"
        self.path_display_mode = "elided"
        self.file_manager_choice = "auto"
        self.file_manager_custom_cmd = ""
        self.custom_manager_warned_this_session = False
        self.show_stats_toggle.setChecked(True)
        self._set_stats_visible(True)
        self.set_theme("system")
        self._update_parallel_mode_controls()
        self._update_parallel_hint()
        self._refresh_file_manager_actions()
        self._on_path_display_changed()
        self._append_log("Preferences reset to defaults.")

    def _set_combo_data(self, combo: QComboBox, value: str) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return

    def _build_option_row(self, checkbox: QCheckBox, tooltip: str) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        info = QToolButton()
        info.setText("?")
        info.setAutoRaise(True)
        info.setToolTip(tooltip)
        info.setCursor(Qt.WhatsThisCursor)

        checkbox.setToolTip(tooltip)
        layout.addWidget(checkbox)
        layout.addWidget(info)
        layout.addStretch()
        return row

    @staticmethod
    def _easyocr_plugin_available() -> bool:
        try:
            importlib.metadata.version("ocrmypdf-easyocr")
        except importlib.metadata.PackageNotFoundError:
            return False
        except Exception:
            return False
        return True

    def _check_runtime_dependencies(self) -> None:
        missing: list[str] = []
        checks = [
            ("ocrmypdf", ["ocrmypdf"]),
            ("tesseract", ["tesseract"]),
            ("Ghostscript", ["gs", "gswin64c", "gswin32c"]),
            ("qpdf", ["qpdf"]),
        ]
        for label, candidates in checks:
            if not any(shutil.which(cmd) for cmd in candidates):
                missing.append(label)

        if not missing:
            return

        details = ", ".join(missing)
        self._append_log(f"Warning: missing OCR dependencies: {details}")
        QMessageBox.warning(
            self,
            "Missing OCR Dependencies",
            "Some required OCR tools are not available in PATH:\n"
            f"{details}\n\n"
            "Install the missing tools, then relaunch for reliable OCR processing.",
        )

    def _update_parallel_mode_controls(self) -> None:
        mode = self.parallel_mode.currentData()
        self.custom_workers.setEnabled(mode == "custom")

    def _resolved_workers(self, pending_count: int) -> int:
        mode = self.parallel_mode.currentData()
        if mode == "auto":
            cpu = os.cpu_count() or 8
            value = min(DEFAULT_WORKERS, max(1, cpu - 2))
        elif mode == "custom":
            value = self.custom_workers.value()
        else:
            value = int(mode)
        value = max(1, min(MAX_WORKERS, value))
        if pending_count > 0:
            value = min(value, pending_count)
        return max(1, value)

    def _update_parallel_hint(self) -> None:
        workers = self._resolved_workers(max(1, self._count_pending()))
        ocr_mode = self.ocr_mode.currentData()
        mode_text = "Force OCR all pages" if ocr_mode == "force" else "Skip pages that already contain text"
        gpu_enabled = bool(self.gpu_checkbox.isChecked()) if hasattr(self, "gpu_checkbox") else False
        backend_text = "GPU plugin enabled (NVIDIA CUDA)" if gpu_enabled else "CPU mode"
        size_enabled = bool(self.optimize_size_checkbox.isChecked()) if hasattr(self, "optimize_size_checkbox") else False
        size_text = "Smaller output optimization ON" if size_enabled else "Standard output size"
        self.parallel_hint.setText(
            f"Using up to {workers} parallel files. {mode_text}. Backend: {backend_text}. {size_text}. "
            "This improves throughput, not single-file speed."
        )

    def _on_gpu_toggle_changed(self, checked: bool) -> None:
        self.use_gpu_acceleration = bool(checked)
        self.settings.setValue("use_gpu_acceleration", self.use_gpu_acceleration)
        self._update_parallel_hint()

    def _on_optimize_size_changed(self, checked: bool) -> None:
        self.optimize_for_size = bool(checked)
        self.settings.setValue("optimize_for_size", self.optimize_for_size)
        self._update_parallel_hint()

    def _on_priority_changed(self) -> None:
        self.priority_mode = self.priority_combo.currentData()
        self.settings.setValue("priority_mode", self.priority_mode)
        for task in self.tasks.values():
            if task.ps_proc is not None and task.status == "Running":
                self._apply_process_priority(task.ps_proc)

    def _apply_process_priority(self, proc: psutil.Process) -> None:
        mode = self.priority_mode
        try:
            if sys.platform.startswith("win"):
                if mode == "low":
                    proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                elif mode == "background":
                    proc.nice(psutil.IDLE_PRIORITY_CLASS)
                else:
                    proc.nice(psutil.NORMAL_PRIORITY_CLASS)
                return

            if mode == "low":
                proc.nice(10)
            elif mode == "background":
                proc.nice(15)
            else:
                proc.nice(0)

            if mode == "background" and sys.platform.startswith("linux"):
                env = os.environ.copy()
                env.pop("LD_LIBRARY_PATH", None)
                subprocess.run(
                    ["ionice", "-c", "3", "-p", str(proc.pid)],
                    check=False,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                )
        except Exception:
            return

    def _pick_pdfs(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select PDF files",
            self.last_dir,
            "PDF files (*.pdf *.PDF)",
        )
        if files:
            self.last_dir = str(Path(files[0]).parent)
            self.settings.setValue("last_dir", self.last_dir)
            self.add_paths(files)

    def _pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select folder", self.last_dir)
        if folder:
            recursive_mode = self._prompt_folder_scan_mode(Path(folder))
            if recursive_mode is None:
                return
            self.folder_scan_recursive = recursive_mode
            self.settings.setValue("folder_scan_recursive", recursive_mode)
            self.last_dir = folder
            self.settings.setValue("last_dir", self.last_dir)
            self.add_paths([folder], recursive_folders=recursive_mode)

    def _prompt_folder_scan_mode(self, folder: Path) -> bool | None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Folder Scan Mode")
        dialog.setIcon(QMessageBox.Question)
        dialog.setText(f"How should OCRestra scan this folder?\n{folder}")
        dialog.setInformativeText(
            "Recursive scans include all subfolders. Top-level scans only files in the selected folder."
        )
        recursive_btn = dialog.addButton("Recursive (All subfolders)", QMessageBox.AcceptRole)
        top_level_btn = dialog.addButton("Top-level only", QMessageBox.ActionRole)
        dialog.addButton(QMessageBox.Cancel)
        if self.folder_scan_recursive:
            dialog.setDefaultButton(recursive_btn)
        else:
            dialog.setDefaultButton(top_level_btn)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked == recursive_btn:
            return True
        if clicked == top_level_btn:
            return False
        return None

    def add_paths(self, raw_paths: list[str], recursive_folders: bool = True) -> None:
        added = 0
        skipped_large = 0
        queue_limit_hit = False
        for pdf_path in self._expand_to_pdfs(raw_paths, recursive_folders=recursive_folders):
            if len(self.tasks) >= MAX_QUEUE_ITEMS:
                queue_limit_hit = True
                break

            path_key = str(pdf_path)
            if path_key in self.path_to_task:
                continue
            try:
                file_size = pdf_path.stat().st_size
            except Exception:
                file_size = 0
            if file_size > MAX_INPUT_FILE_BYTES:
                skipped_large += 1
                self._append_log(
                    f"Skipped oversized PDF ({_format_bytes(file_size)}): {pdf_path}"
                )
                continue

            task_id = uuid.uuid4().hex[:12]
            row = self.table.rowCount()
            self.table.insertRow(row)

            output_path = self._next_output_path(pdf_path.parent / "OCR_Output", pdf_path.stem)
            task = TaskItem(
                task_id=task_id,
                input_path=pdf_path,
                output_path=output_path,
                temp_dir=TEMP_ROOT / task_id,
                log_file=LOG_ROOT / f"{task_id}.log",
                row=row,
            )
            self.tasks[task_id] = task
            self.path_to_task[path_key] = task_id

            display_path = self._display_input_path(pdf_path)
            self.table.setItem(row, TABLE_COL_INPUT, QTableWidgetItem(display_path))
            self.table.item(row, TABLE_COL_INPUT).setToolTip(path_key)
            self.table.setItem(row, TABLE_COL_STATUS, QTableWidgetItem("Queued"))
            self.table.setItem(row, TABLE_COL_RESULT, QTableWidgetItem(""))

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setFormat("%p%")
            bar.setTextVisible(True)
            bar.setStyleSheet(self._progress_style_for_value(0))
            self.table.setCellWidget(row, TABLE_COL_PROGRESS, bar)

            action_button = QPushButton("Cancel")
            action_button.clicked.connect(lambda _checked, tid=task_id: self._on_action_button_clicked(tid))
            self.table.setCellWidget(row, TABLE_COL_ACTION, action_button)
            self._refresh_action_button(task)

            log_button = QPushButton("View Log")
            log_button.clicked.connect(lambda _checked, tid=task_id: self._on_view_log_clicked(tid))
            self.table.setCellWidget(row, TABLE_COL_LOG, log_button)
            self._set_log_button(task, enabled=False)
            added += 1

        if added:
            self._append_log(f"Queued {added} PDF file(s).")
        elif skipped_large == 0 and not queue_limit_hit:
            self._append_log("No new PDFs found in dropped/selected paths.")
        if skipped_large:
            self._append_log(
                f"Skipped {skipped_large} file(s) larger than {_format_bytes(MAX_INPUT_FILE_BYTES)}."
            )
        if queue_limit_hit:
            self._append_log(
                f"Queue limit reached ({MAX_QUEUE_ITEMS} items). Add fewer files per batch."
            )
            QMessageBox.warning(
                self,
                "Queue Limit Reached",
                f"Maximum queue size is {MAX_QUEUE_ITEMS} files.\n"
                "Start/clear current jobs, then add more files.",
            )
        self._sync_empty_state_overlay()
        self._update_parallel_hint()
        self._update_metrics_labels()
        self._save_queue_state()

    def _expand_to_pdfs(self, raw_paths: list[str], recursive_folders: bool = True) -> list[Path]:
        discovered: list[Path] = []
        seen: set[str] = set()
        hit_discovery_limit = False
        hit_depth_limit = False
        for raw in raw_paths:
            path = Path(raw).expanduser()
            if not path.exists():
                continue
            if path.is_file() and path.suffix.lower() == ".pdf":
                resolved = path.resolve()
                key = str(resolved)
                if key not in seen:
                    discovered.append(resolved)
                    seen.add(key)
                    if len(discovered) >= MAX_DISCOVERED_PDFS:
                        hit_discovery_limit = True
                        break
                continue
            if path.is_dir():
                if not recursive_folders:
                    try:
                        for child in path.iterdir():
                            if not child.is_file() or child.suffix.lower() != ".pdf":
                                continue
                            resolved = child.resolve()
                            key = str(resolved)
                            if key in seen:
                                continue
                            discovered.append(resolved)
                            seen.add(key)
                            if len(discovered) >= MAX_DISCOVERED_PDFS:
                                hit_discovery_limit = True
                                break
                    except Exception:
                        continue
                    if hit_discovery_limit:
                        break
                    continue
                try:
                    for root, dirs, files in os.walk(path, topdown=True, followlinks=False):
                        root_path = Path(root)
                        try:
                            rel_parts = root_path.relative_to(path).parts
                            depth = len(rel_parts)
                        except Exception:
                            depth = 0
                        if depth >= MAX_SCAN_DEPTH:
                            dirs[:] = []
                            hit_depth_limit = True
                            continue
                        dirs[:] = [name for name in dirs if not (root_path / name).is_symlink()]
                        for filename in files:
                            if not filename.lower().endswith(".pdf"):
                                continue
                            file_path = root_path / filename
                            if not file_path.is_file():
                                continue
                            resolved = file_path.resolve()
                            key = str(resolved)
                            if key not in seen:
                                discovered.append(resolved)
                                seen.add(key)
                                if len(discovered) >= MAX_DISCOVERED_PDFS:
                                    hit_discovery_limit = True
                                    break
                        if hit_discovery_limit:
                            break
                except Exception:
                    continue
            if hit_discovery_limit:
                break
        if hit_discovery_limit:
            self._append_log(
                f"Discovery limit reached at {MAX_DISCOVERED_PDFS} PDFs. Narrow your selection."
            )
        if hit_depth_limit:
            self._append_log(
                f"Skipped folders deeper than {MAX_SCAN_DEPTH} levels during scan."
            )
        return discovered

    def clear_tasks(self) -> None:
        if any(task.status == "Running" for task in self.tasks.values()):
            QMessageBox.warning(self, "Jobs Running", "Cancel active jobs before clearing the list.")
            return
        self.tasks.clear()
        self.path_to_task.clear()
        self.table.setRowCount(0)
        self.total_batch = 0
        self.finished_batch = 0
        self.batch_running = False
        self._update_batch_progress()
        self._update_parallel_hint()
        self._update_metrics_labels()
        self._sync_empty_state_overlay()
        self._append_log("Cleared queued tasks.")
        self._save_queue_state()

    def start_batch(self) -> None:
        if any(task.status == "Running" for task in self.tasks.values()):
            QMessageBox.information(self, "Already Running", "Some jobs are already running.")
            return

        pending = [task for task in self.tasks.values() if task.status in {"Queued", "Failed", "Canceled"}]
        if not pending:
            QMessageBox.information(self, "Nothing to process", "Add PDFs first.")
            return
        if self.gpu_checkbox.isChecked() and not self._easyocr_plugin_available():
            QMessageBox.warning(
                self,
                "GPU Plugin Missing",
                "GPU acceleration requires the ocrmypdf-easyocr plugin in this virtual environment.\n\n"
                "Install in the app venv, then relaunch:\n"
                "  python -m pip install ocrmypdf-easyocr",
            )
            return
        if self.ocr_mode.currentData() == "force" and not self._confirm_force_ocr_risk(len(pending)):
            return

        self.active_run_token += 1
        self.total_batch = len(pending)
        self.finished_batch = 0
        self.batch_running = True
        self.start_button.setEnabled(False)
        self.current_worker_limit = self._resolved_workers(len(pending))
        self.current_force_ocr = self.ocr_mode.currentData() == "force"
        self.current_use_gpu = bool(self.gpu_checkbox.isChecked())
        self.current_optimize_for_size = bool(self.optimize_size_checkbox.isChecked())
        self.settings.setValue("parallel_mode", self.parallel_mode.currentData())
        self.settings.setValue("custom_workers", self.custom_workers.value())
        self.settings.setValue("ocr_mode", self.ocr_mode.currentData())
        self.settings.setValue("use_gpu_acceleration", self.current_use_gpu)
        self.settings.setValue("optimize_for_size", self.current_optimize_for_size)

        batch_stamp = Path.cwd().name + "_" + uuid.uuid4().hex[:8]
        self.batch_log_dir = LOG_ROOT / batch_stamp
        self.batch_log_dir.mkdir(parents=True, exist_ok=True)

        for task in pending:
            task.status = "Queued"
            task.run_token = self.active_run_token
            task.counted = False
            task.metrics.clear()
            task.used_fallback = False
            task.peak_cpu_percent = 0.0
            task.peak_rss_bytes = 0
            task.progress_value = 0
            self._set_status(task, "Queued")
            self._set_result(task, "")
            self._set_progress(task, 0)
            self._refresh_action_button(task)

        self._append_log(
            "Starting batch: "
            f"{self.total_batch} file(s), {self.current_worker_limit} parallel workers, "
            f"{'force OCR' if self.current_force_ocr else 'smart OCR'} mode, "
            f"{'GPU plugin enabled' if self.current_use_gpu else 'CPU mode'}, "
            f"{'size optimization enabled' if self.current_optimize_for_size else 'standard size profile'}."
        )
        self._schedule_tasks()
        self._update_batch_progress()
        self._update_metrics_labels()

    def _confirm_force_ocr_risk(self, file_count: int) -> bool:
        answer = QMessageBox.warning(
            self,
            "Force OCR Warning",
            "Force OCR will rasterize pages even when text already exists.\n\n"
            "This can significantly increase file size and processing time "
            "(especially for PDFs already OCR'd by tools like NAPS2).\n\n"
            f"Continue with Force OCR for {file_count} file(s)?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def _schedule_tasks(self) -> None:
        if not self.batch_running:
            return
        running = [task for task in self.tasks.values() if task.status == "Running"]
        slots = self.current_worker_limit - len(running)
        if slots <= 0:
            return
        queued_tasks = [
            task
            for task in self.tasks.values()
            if task.status == "Queued" and task.run_token == self.active_run_token
        ]
        for task in queued_tasks[:slots]:
            self._start_task(task)

    def _start_task(self, task: TaskItem) -> None:
        if not task.input_path.exists():
            task.status = "Failed"
            self._set_status(task, "Failed")
            self._set_result(task, "Input file missing")
            self._set_progress(task, 0)
            self._refresh_action_button(task)
            self._append_log(f"Input file not found: {task.input_path}")
            self._mark_batch_progress(task)
            return
        try:
            input_size = task.input_path.stat().st_size
        except Exception:
            input_size = 0
        if input_size > MAX_INPUT_FILE_BYTES:
            task.status = "Failed"
            self._set_status(task, "Failed")
            self._set_result(
                task,
                f"Input exceeds limit ({_format_bytes(MAX_INPUT_FILE_BYTES)} max)",
            )
            self._set_progress(task, 0)
            self._refresh_action_button(task)
            self._append_log(
                f"Input too large ({_format_bytes(input_size)}): {task.input_path}"
            )
            self._mark_batch_progress(task)
            return

        try:
            task.output_path = self._next_output_path(task.input_path.parent / "OCR_Output", task.input_path.stem)
        except Exception as exc:
            task.status = "Failed"
            self._set_status(task, "Failed")
            self._set_result(task, f"Output path setup failed: {exc}")
            self._set_progress(task, 0)
            self._refresh_action_button(task)
            self._append_log(f"Failed to prepare output path for {task.input_path}: {exc}")
            self._mark_batch_progress(task)
            return
        if self.batch_log_dir is None:
            self.batch_log_dir = LOG_ROOT
        safe_name = _safe_file_part(task.input_path.stem)
        task.log_file = self.batch_log_dir / f"{safe_name}_{task.task_id}.log"
        task.temp_dir = TEMP_ROOT / task.task_id

        config = {
            "task_id": task.task_id,
            "input_pdf": str(task.input_path),
            "output_pdf": str(task.output_path),
            "log_file": str(task.log_file),
            "temp_dir": str(task.temp_dir),
            "force_ocr": self.current_force_ocr,
            "use_gpu": self.current_use_gpu,
            "optimize_for_size": self.current_optimize_for_size,
        }
        task.queue = mp.Queue()
        task.process = mp.Process(target=run_ocr_job, args=(config, task.queue), name=f"ocr-{task.task_id}")
        task.process.start()
        task.ps_proc = psutil.Process(task.process.pid)
        task.ps_proc.cpu_percent(None)
        self._apply_process_priority(task.ps_proc)
        task.status = "Running"
        task.progress_value = 1
        task.metrics["started_monotonic"] = time.monotonic()
        task.metrics["estimated_seconds"] = self._estimate_task_duration(task)
        task.metrics["last_progress_tick"] = time.monotonic()

        self._set_status(task, "Running")
        self._set_result(task, "In progress...")
        self._set_log_button(task, enabled=True)
        self._set_progress(task, 1)
        self._refresh_action_button(task)
        self._append_log(f"Started {task.input_path} (PID {task.process.pid})")

    def _poll_workers(self) -> None:
        self._advance_running_progress()
        for task in list(self.tasks.values()):
            self._drain_task_queue(task)
            if task.status == "Running" and task.process is not None and not task.process.is_alive():
                self._finalize_task(task, False, "Worker process exited unexpectedly.")
        self._schedule_tasks()
        if self.batch_running:
            self._update_batch_progress()

    def _drain_task_queue(self, task: TaskItem) -> None:
        if task.queue is None:
            return
        while True:
            try:
                event = task.queue.get_nowait()
            except queue.Empty:
                break
            except Exception:
                break
            self._handle_worker_event(task, event)

    def _handle_worker_event(self, task: TaskItem, event: dict) -> None:
        event_type = event.get("type")
        if event_type == "log":
            message = event.get("message", "")
            self._track_task_log_metrics(task, message)
            self._append_log(message, task.task_id)
            return
        if event_type == "status":
            status = event.get("status", "Running")
            self._set_status(task, status)
            return
        if event_type == "done":
            if task.status == "Canceled":
                return
            success = bool(event.get("success", False))
            if success:
                result = event.get("output_pdf", "")
                if result:
                    task.output_path = Path(result)
                task.used_fallback = bool(event.get("used_fallback", False))
                self._finalize_task(task, True, result, None, event)
            else:
                error = event.get("error", "Unknown OCR error")
                self._finalize_task(task, False, error, "Failed", event)

    def _finalize_task(
        self,
        task: TaskItem,
        success: bool,
        result_text: str,
        status_text: str | None = None,
        metrics: dict | None = None,
    ) -> None:
        if task.status in {"Done", "Failed", "Canceled"}:
            return
        merged_metrics = dict(task.metrics)
        if metrics:
            merged_metrics.update(metrics)
        task.metrics = merged_metrics

        if success and status_text is None:
            skipped = self._was_effectively_skipped(task)
            base = "Skipped (Already Searchable)" if skipped else "Done"
            if task.used_fallback:
                base = f"{base} (tmp fallback)"
            task.status = base
        else:
            task.status = status_text or ("Done" if success else "Failed")

        self._set_status(task, task.status)
        self._set_result(task, result_text)
        self._set_progress(task, 100 if success else 0)
        self._refresh_action_button(task)
        self._close_task_process(task)

        if merged_metrics:
            self._append_metrics_to_log(task)
        self._mark_batch_progress(task)
        self._update_metrics_labels()

    def _mark_batch_progress(self, task: TaskItem) -> None:
        if task.run_token == self.active_run_token and not task.counted:
            task.counted = True
            self.finished_batch += 1
        self._update_batch_progress()
        if self.batch_running and self.finished_batch >= self.total_batch:
            self.batch_running = False
            self.start_button.setEnabled(True)
            self._append_log("Batch completed.")

    def cancel_task(self, task_id: str) -> None:
        task = self.tasks.get(task_id)
        if task is None:
            return
        if task.status == "Queued":
            task.status = "Canceled"
            self._set_status(task, "Canceled")
            self._set_result(task, "Canceled before start")
            self._set_progress(task, 0)
            self._refresh_action_button(task)
            self._mark_batch_progress(task)
            return
        if task.status != "Running":
            return

        self._set_status(task, "Canceling...")
        self._append_log(f"Cancel requested for {task.input_path}")
        self._terminate_task_process(task)
        self._cleanup_task_files(task)
        task.status = "Canceled"
        self._set_status(task, "Canceled")
        self._set_result(task, "Canceled by user")
        self._set_progress(task, 0)
        self._refresh_action_button(task)
        self._append_cancel_to_log(task)
        self._mark_batch_progress(task)

    def cancel_selected(self) -> None:
        for task_id in self._selected_task_ids():
            self.cancel_task(task_id)
        self._update_metrics_labels()

    def cancel_all(self) -> None:
        for task in list(self.tasks.values()):
            if task.status in {"Queued", "Running"}:
                self.cancel_task(task.task_id)
        self._update_metrics_labels()

    def _selected_task_ids(self) -> list[str]:
        ids: list[str] = []
        seen_rows: set[int] = set()
        for item in self.table.selectedItems():
            row = item.row()
            if row in seen_rows:
                continue
            seen_rows.add(row)
            task_id = self._task_id_for_row(row)
            if task_id:
                ids.append(task_id)
        return ids

    def _show_table_context_menu(self, pos) -> None:
        row = self.table.indexAt(pos).row()
        if row < 0:
            row = self.table.currentRow()
        if row < 0:
            return
        task_id = self._task_id_for_row(row)
        if not task_id:
            return
        task = self.tasks.get(task_id)
        if task is None:
            return

        menu = QMenu(self)
        copy_input = menu.addAction("Copy Input Path")
        copy_output = menu.addAction("Copy Output Path")
        copy_log = menu.addAction("Copy Log Path")
        menu.addSeparator()
        open_folder = menu.addAction("Open Output Folder")
        view_log = menu.addAction("View Log")

        if not task.log_file.exists():
            view_log.setEnabled(False)
        if not task.output_path.exists():
            copy_output.setEnabled(False)

        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == copy_input:
            self._copy_to_clipboard(str(task.input_path), "Copied input path.")
        elif chosen == copy_output:
            self._copy_to_clipboard(str(task.output_path), "Copied output path.")
        elif chosen == copy_log:
            self._copy_to_clipboard(str(task.log_file), "Copied log path.")
        elif chosen == open_folder:
            self._open_output_folder(task)
        elif chosen == view_log:
            self._open_log_dialog(task)

    def _copy_to_clipboard(self, value: str, feedback: str) -> None:
        QApplication.clipboard().setText(value)
        self._append_log(feedback)

    def _task_id_for_row(self, row: int) -> str | None:
        for task_id, task in self.tasks.items():
            if task.row == row:
                return task_id
        return None

    @staticmethod
    def _is_path_within(base: Path, path: Path) -> bool:
        try:
            base_resolved = base.resolve()
            path_resolved = path.resolve()
        except Exception:
            return False
        return path_resolved == base_resolved or base_resolved in path_resolved.parents

    def _display_input_path(self, path: Path) -> str:
        mode = self.path_display_combo.currentData() if hasattr(self, "path_display_combo") else self.path_display_mode
        full = str(path)
        if mode == "full":
            return full
        if mode == "name":
            return path.name

        parts = path.parts
        if len(parts) <= 4:
            return full
        if path.anchor:
            prefix = path.anchor.rstrip("/\\")
            tail = "/".join(parts[-3:])
            return f"{prefix}/.../{tail}"
        tail = "/".join(parts[-3:])
        return f".../{tail}"

    def _on_path_display_changed(self) -> None:
        self.path_display_mode = self.path_display_combo.currentData()
        self.settings.setValue("path_display_mode", self.path_display_mode)
        for task in self.tasks.values():
            item = self.table.item(task.row, TABLE_COL_INPUT)
            if item is None:
                continue
            item.setText(self._display_input_path(task.input_path))
            item.setToolTip(str(task.input_path))

    def _close_task_process(self, task: TaskItem) -> None:
        if task.process is not None:
            try:
                task.process.join(timeout=1.0)
                if task.process.is_alive():
                    task.process.terminate()
                    task.process.join(timeout=0.5)
            except Exception:
                pass
            task.process = None
        if task.queue is not None:
            try:
                task.queue.close()
            except Exception:
                pass
            task.queue = None
        task.ps_proc = None

    def _terminate_task_process(self, task: TaskItem) -> None:
        proc = task.process
        if proc is None:
            self._close_task_process(task)
            return
        try:
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=1.0)
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=1.0)
        except Exception:
            pass
        self._close_task_process(task)

    def _cleanup_task_files(self, task: TaskItem) -> None:
        try:
            if self._is_path_within(TEMP_ROOT, task.temp_dir):
                shutil.rmtree(task.temp_dir, ignore_errors=True)
        except Exception:
            pass
        try:
            output_root = task.input_path.parent / "OCR_Output"
            is_safe_output = (
                task.output_path.suffix.lower() == ".pdf"
                and self._is_path_within(output_root, task.output_path)
            )
            if is_safe_output and task.output_path.exists() and not task.output_path.is_symlink():
                task.output_path.unlink()
        except Exception:
            pass

    def _set_status(self, task: TaskItem, value: str) -> None:
        item = self.table.item(task.row, TABLE_COL_STATUS)
        if item is not None:
            item.setText(value)

    def _track_task_log_metrics(self, task: TaskItem, message: str) -> None:
        lowered = message.lower()
        if "skipping all processing on this page" in lowered:
            task.metrics["skip_page_hits"] = int(task.metrics.get("skip_page_hits", 0)) + 1

        if "parsing" in lowered and "with hocrparser" in lowered:
            match = re.search(r"Parsing\s+(\d+)\s+pages?\s+with HocrParser", message)
            if match:
                task.metrics["hocr_pages"] = int(match.group(1))

    def _was_effectively_skipped(self, task: TaskItem) -> bool:
        hocr_pages = int(task.metrics.get("hocr_pages", 0))
        skip_hits = int(task.metrics.get("skip_page_hits", 0))
        if hocr_pages > 0:
            return False
        return skip_hits > 0

    def _set_result(self, task: TaskItem, value: str) -> None:
        item = self.table.item(task.row, TABLE_COL_RESULT)
        if item is not None:
            item.setText(value)
            item.setToolTip(value)

    def _set_log_button(self, task: TaskItem, enabled: bool) -> None:
        button = self.table.cellWidget(task.row, TABLE_COL_LOG)
        if isinstance(button, QPushButton):
            button.setText("View Log")
            button.setEnabled(enabled)
            button.setMinimumWidth(94)
            button.setToolTip(str(task.log_file))

    def _set_progress(self, task: TaskItem, value: int) -> None:
        bar = self.table.cellWidget(task.row, TABLE_COL_PROGRESS)
        if not isinstance(bar, QProgressBar):
            return
        if bar.maximum() == 0:
            bar.setRange(0, 100)
        value = max(0, min(100, value))
        task.progress_value = value
        bar.setValue(value)
        if task.status == "Running" and value >= 95 and value < 100:
            bar.setFormat(f"~{value}% (Finalizing/Optimizing)")
        else:
            bar.setFormat(f"{value}%")
        bar.setStyleSheet(self._progress_style_for_value(value))

    def _set_action_button(self, task: TaskItem, label: str, enabled: bool) -> None:
        button = self.table.cellWidget(task.row, TABLE_COL_ACTION)
        if isinstance(button, QPushButton):
            button.setText(label)
            button.setEnabled(enabled)
            button.setMinimumWidth(112)

    def _refresh_action_button(self, task: TaskItem) -> None:
        status = task.status
        if status in {"Queued", "Running"}:
            self._set_action_button(task, "Cancel", True)
            return
        if status.startswith("Done") or status.startswith("Skipped"):
            self._set_action_button(task, "Open Folder", True)
            return
        if status == "Canceling...":
            self._set_action_button(task, "Canceling...", False)
            return
        self._set_action_button(task, status, False)

    def _on_action_button_clicked(self, task_id: str) -> None:
        task = self.tasks.get(task_id)
        if task is None:
            return
        if task.status in {"Queued", "Running"}:
            self.cancel_task(task_id)
            return
        if task.status.startswith("Done") or task.status.startswith("Skipped"):
            self._open_output_folder(task)

    def _on_view_log_clicked(self, task_id: str) -> None:
        task = self.tasks.get(task_id)
        if task is None:
            return
        if not task.log_file.exists():
            QMessageBox.information(self, "Log Not Ready", "This task does not have a log file yet.")
            return
        self._open_log_dialog(task)

    def _open_log_dialog(self, task: TaskItem) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Log - {task.input_path.name}")
        dialog.resize(960, 640)
        layout = QVBoxLayout(dialog)
        viewer = QPlainTextEdit(dialog)
        viewer.setReadOnly(True)
        try:
            viewer.setPlainText(task.log_file.read_text(encoding="utf-8", errors="replace"))
        except Exception as exc:
            viewer.setPlainText(f"Failed to read log file:\n{exc}")
        layout.addWidget(viewer)
        dialog.exec()

    def _open_output_folder(self, task: TaskItem) -> None:
        candidates = [
            task.output_path.parent,
            task.input_path.parent / "OCR_Output",
            task.input_path.parent,
        ]
        target = next((path for path in candidates if path.exists()), task.input_path.parent)
        opened = self._open_in_file_manager(target)
        if not opened:
            opened = self._open_with_system_default(target)
        if not opened:
            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        if not opened:
            QMessageBox.warning(self, "Open Output Folder", f"Could not open {target}")

    def _file_manager_options_for_platform(self) -> list[tuple[str, str, list[str] | None]]:
        if sys.platform.startswith("win"):
            return FILE_MANAGER_OPTIONS_WINDOWS
        if sys.platform == "darwin":
            return FILE_MANAGER_OPTIONS_MACOS
        return FILE_MANAGER_OPTIONS_LINUX

    def _file_manager_available(self, manager_id: str, command: list[str] | None) -> bool:
        if manager_id in {"auto", "system"}:
            return True
        if manager_id == "custom":
            valid, _error = self._validate_custom_file_manager_template(self.file_manager_custom_cmd)
            return valid
        if command is None or len(command) == 0:
            return False
        executable = command[0]
        if manager_id == "explorer":
            return True
        return shutil.which(executable) is not None

    @staticmethod
    def _contains_disallowed_shell_chars(template: str) -> bool:
        disallowed_parts = (";", "&&", "||", "|", "`", "$(", "\n", "\r", "\x00")
        return any(part in template for part in disallowed_parts)

    def _validate_custom_file_manager_template(self, template: str) -> tuple[bool, str]:
        value = template.strip()
        if not value:
            return False, "Command is empty."
        if len(value) > MAX_CUSTOM_FILE_MANAGER_CMD_LEN:
            return False, f"Command is too long ({MAX_CUSTOM_FILE_MANAGER_CMD_LEN} chars max)."
        if "{path}" not in value:
            return False, "Command must include a {path} placeholder."
        if self._contains_disallowed_shell_chars(value):
            return False, "Command contains blocked shell control characters."

        try:
            parts = shlex.split(value, posix=not sys.platform.startswith("win"))
        except Exception:
            return False, "Command could not be parsed."
        if not parts:
            return False, "Command could not be parsed."

        executable = parts[0]
        blocked_launchers = {"sh", "bash", "zsh", "fish", "cmd", "powershell", "pwsh"}
        if executable.lower() in blocked_launchers:
            return False, "Shell launchers are blocked for custom commands."
        if Path(executable).is_absolute():
            if not Path(executable).exists():
                return False, "Executable path does not exist."
        elif shutil.which(executable) is None:
            return False, "Executable is not installed or not in PATH."
        return True, ""

    def _render_custom_file_manager_command(self, template: str, path: Path) -> list[str] | None:
        valid, _error = self._validate_custom_file_manager_template(template)
        if not valid:
            return None
        try:
            parts = shlex.split(template, posix=not sys.platform.startswith("win"))
        except Exception:
            return None
        rendered: list[str] = []
        path_text = str(path)
        for part in parts:
            rendered.append(part.replace("{path}", path_text))
        return rendered

    def _refresh_file_manager_actions(self) -> None:
        if not hasattr(self, "file_manager_actions"):
            return
        available_ids: set[str] = set()
        for manager_id, _label, command in self._file_manager_options_for_platform():
            action = self.file_manager_actions.get(manager_id)
            if action is None:
                continue
            available = self._file_manager_available(manager_id, command)
            action.setEnabled(available)
            if available:
                available_ids.add(manager_id)
        custom_action = self.file_manager_actions.get("custom")
        if custom_action is not None:
            custom_available, _custom_error = self._validate_custom_file_manager_template(self.file_manager_custom_cmd)
            custom_action.setEnabled(custom_available)
            if custom_available:
                available_ids.add("custom")
        if self.file_manager_choice not in available_ids and self.file_manager_choice != "custom":
            self.file_manager_choice = "auto"
        if self.file_manager_choice == "custom" and not self.file_manager_custom_cmd:
            self.file_manager_choice = "auto"
        selected_action = self.file_manager_actions.get(self.file_manager_choice)
        if selected_action is not None:
            selected_action.setChecked(True)

    def _set_file_manager_choice(self, manager_id: str) -> None:
        if manager_id == "custom" and not self.file_manager_custom_cmd:
            self._set_custom_file_manager_command()
            if not self.file_manager_custom_cmd:
                manager_id = "auto"
        if manager_id == "custom":
            valid, _error = self._validate_custom_file_manager_template(self.file_manager_custom_cmd)
            if not valid:
                manager_id = "auto"
        self.file_manager_choice = manager_id
        self.settings.setValue("file_manager_choice", self.file_manager_choice)
        self._refresh_file_manager_actions()

    def _set_custom_file_manager_command(self) -> None:
        current = self.file_manager_custom_cmd or "dolphin {path}"
        text, ok = QInputDialog.getText(
            self,
            "Custom File Manager",
            "Enter command template (use {path} placeholder):",
            text=current,
        )
        if not ok:
            return
        value = text.strip()
        if not value:
            self.file_manager_custom_cmd = ""
            self.file_manager_choice = "auto"
            self.settings.setValue("file_manager_custom_cmd", "")
            self.settings.setValue("file_manager_choice", "auto")
            self._refresh_file_manager_actions()
            return
        if "{path}" not in value:
            value = value + " {path}"
        valid, error = self._validate_custom_file_manager_template(value)
        if not valid:
            QMessageBox.warning(self, "Invalid Command", error)
            return
        self.file_manager_custom_cmd = value
        self.file_manager_choice = "custom"
        self.custom_manager_warned_this_session = False
        self.settings.setValue("file_manager_custom_cmd", self.file_manager_custom_cmd)
        self.settings.setValue("file_manager_choice", self.file_manager_choice)
        self._refresh_file_manager_actions()

    def _open_in_file_manager(self, path: Path) -> bool:
        env = os.environ.copy()
        env.pop("LD_LIBRARY_PATH", None)

        choice = self.file_manager_choice
        if choice == "custom" and self.file_manager_custom_cmd:
            command = self._render_custom_file_manager_command(self.file_manager_custom_cmd, path)
            if not command:
                return False
            if not self.custom_manager_warned_this_session:
                answer = QMessageBox.question(
                    self,
                    "Custom File Manager Command",
                    "Run the configured custom file-manager command for this session?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if answer != QMessageBox.Yes:
                    return False
                self.custom_manager_warned_this_session = True
            return self._run_file_manager_command(command, env)

        if choice == "auto":
            for manager_id, _label, cmd in self._file_manager_options_for_platform():
                if manager_id in {"auto", "system", "custom"}:
                    continue
                if not self._file_manager_available(manager_id, cmd):
                    continue
                rendered = [part.replace("{path}", str(path)) for part in (cmd or [])]
                if rendered and self._run_file_manager_command(rendered, env):
                    return True
            return False

        if choice == "system":
            return False

        options = {manager_id: cmd for manager_id, _label, cmd in self._file_manager_options_for_platform()}
        cmd = options.get(choice)
        if cmd is None:
            return False
        rendered = [part.replace("{path}", str(path)) for part in cmd]
        return self._run_file_manager_command(rendered, env)

    def _open_with_system_default(self, path: Path) -> bool:
        env = os.environ.copy()
        env.pop("LD_LIBRARY_PATH", None)
        if sys.platform.startswith("win"):
            command = ["explorer", str(path)]
        elif sys.platform == "darwin":
            command = ["open", str(path)]
        else:
            command = ["xdg-open", str(path)]
        return self._run_file_manager_command(command, env)

    @staticmethod
    def _run_file_manager_command(
        command: list[str],
        env: dict[str, str],
    ) -> bool:
        try:
            popen_kwargs = {
                "env": env,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
            if sys.platform.startswith("win"):
                popen_kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                popen_kwargs["start_new_session"] = True
            proc = subprocess.Popen(command, **popen_kwargs)
            time.sleep(0.2)
            rc = proc.poll()
            if rc is not None and rc != 0:
                return False
            return True
        except Exception:
            return False

    def _progress_style_for_value(self, value: int) -> str:
        if value <= 25:
            color = "#d64545"
        elif value <= 50:
            color = "#de8f2a"
        elif value <= 75:
            color = "#d4b830"
        elif value <= 99:
            color = "#3b82f6"
        else:
            color = "#2fa84f"
        base = self.palette().color(QPalette.Base).name()
        border = self.palette().color(QPalette.Mid).name()
        return (
            f"QProgressBar {{ border: 1px solid {border}; border-radius: 6px; text-align: center; background: {base}; }}"
            f"QProgressBar::chunk {{ background: {color}; border-radius: 5px; }}"
        )

    @staticmethod
    def _resource_health(value: float, green_limit: float, yellow_limit: float) -> tuple[str, str]:
        if value < green_limit:
            return "Green", "#2fa84f"
        if value < yellow_limit:
            return "Yellow", "#d4b830"
        return "Red", "#d64545"

    @staticmethod
    def _query_nvidia_gpu_metrics() -> tuple[float, int, int, int] | None:
        if shutil.which("nvidia-smi") is None:
            return None
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except Exception:
            return None

        utilization_values: list[float] = []
        used_mib_total = 0
        total_mib_total = 0
        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = [part.strip() for part in line.split(",")]
            if len(parts) < 3:
                continue
            try:
                util = float(parts[0])
                used_mib = int(float(parts[1]))
                total_mib = int(float(parts[2]))
            except Exception:
                continue
            utilization_values.append(util)
            used_mib_total += max(0, used_mib)
            total_mib_total += max(0, total_mib)

        if not utilization_values:
            return None
        return max(utilization_values), used_mib_total, total_mib_total, len(utilization_values)

    def _auto_adjust_table_columns(self) -> None:
        available = max(620, self.table.viewport().width())
        status_w = 96
        progress_w = 188
        log_w = 98
        action_w = 120
        fixed_total = status_w + progress_w + action_w + log_w
        stretch = max(360, available - fixed_total - 10)
        input_w = max(220, int(stretch * 0.62))
        result_w = max(140, stretch - input_w)

        self.table.setColumnWidth(TABLE_COL_STATUS, status_w)
        self.table.setColumnWidth(TABLE_COL_PROGRESS, progress_w)
        self.table.setColumnWidth(TABLE_COL_ACTION, action_w)
        self.table.setColumnWidth(TABLE_COL_LOG, log_w)
        self.table.setColumnWidth(TABLE_COL_INPUT, input_w)
        self.table.setColumnWidth(TABLE_COL_RESULT, result_w)

    def _set_stats_visible(self, visible: bool) -> None:
        if hasattr(self, "stats_frame"):
            self.stats_frame.setVisible(visible)
        self.settings.setValue("show_stats", bool(visible))

    def _update_splitter_orientation(self) -> None:
        if not hasattr(self, "main_splitter"):
            return
        desired = Qt.Vertical if self.width() < 1120 else Qt.Horizontal
        if self.main_splitter.orientation() == desired:
            return
        self.main_splitter.setOrientation(desired)
        if desired == Qt.Horizontal:
            self.main_splitter.setSizes([480, 880])
        else:
            self.main_splitter.setSizes([420, 580])

    def _sync_empty_state_overlay(self) -> None:
        if not hasattr(self, "empty_state_overlay"):
            return
        viewport = self.table.viewport()
        self.empty_state_overlay.setGeometry(viewport.rect())
        visible = self.table.rowCount() == 0
        self.empty_state_overlay.setVisible(visible)
        if visible:
            self.empty_state_overlay.raise_()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is getattr(self, "table_viewport", None) and event.type() in {QEvent.Resize, QEvent.Show}:
            self._sync_empty_state_overlay()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_splitter_orientation()
        self._auto_adjust_table_columns()
        self._sync_empty_state_overlay()

    def _estimate_task_duration(self, task: TaskItem) -> float:
        try:
            size_bytes = task.input_path.stat().st_size
        except Exception:
            size_bytes = 5 * 1024 * 1024
        size_mb = max(1.0, size_bytes / (1024 * 1024))
        return max(8.0, min(240.0, size_mb * 2.2))

    def _advance_running_progress(self) -> None:
        now = time.monotonic()
        for task in self.tasks.values():
            if task.status != "Running":
                continue
            started = float(task.metrics.get("started_monotonic", now))
            estimated = float(task.metrics.get("estimated_seconds", 30.0))
            elapsed = max(0.0, now - started)
            target = int(min(95.0, (elapsed / max(1.0, estimated)) * 95.0))
            last_tick = float(task.metrics.get("last_progress_tick", 0.0))
            if target <= task.progress_value:
                if now - last_tick < 1.0:
                    continue
                target = min(95, task.progress_value + 1)
            task.metrics["last_progress_tick"] = now
            self._set_progress(task, target)

    def _count_pending(self) -> int:
        return sum(1 for task in self.tasks.values() if task.status == "Queued")

    def _update_batch_progress(self) -> None:
        if self.total_batch <= 0:
            self.batch_progress.setValue(0)
            self.batch_progress.setFormat("0%")
            self.batch_progress.setStyleSheet(self._progress_style_for_value(0))
            self.batch_label.setText("Batch progress: 0/0")
            return
        active_tasks = [
            task for task in self.tasks.values() if task.run_token == self.active_run_token
        ]
        if not active_tasks:
            pct = int((self.finished_batch / self.total_batch) * 100)
        else:
            total = 0
            for task in active_tasks:
                if task.status in {
                    "Done",
                    "Done (tmp fallback)",
                    "Skipped (Already Searchable)",
                    "Skipped (Already Searchable) (tmp fallback)",
                    "Failed",
                    "Canceled",
                }:
                    total += 100
                else:
                    total += max(0, min(100, task.progress_value))
            pct = int(total / len(active_tasks))
        self.batch_progress.setValue(pct)
        self.batch_progress.setFormat(f"{pct}%")
        self.batch_progress.setStyleSheet(self._progress_style_for_value(pct))
        self.batch_label.setText(f"Batch progress: {self.finished_batch}/{self.total_batch}")

    def _update_metrics_labels(self) -> None:
        try:
            app_cpu = self.app_proc.cpu_percent(None)
            app_ram = self.app_proc.memory_info().rss
        except Exception:
            app_cpu = 0.0
            app_ram = 0
        sys_cpu = psutil.cpu_percent(None)
        sys_ram = psutil.virtual_memory().percent

        running = 0
        queued = 0
        for task in self.tasks.values():
            if task.status == "Running":
                running += 1
                if task.ps_proc is not None:
                    try:
                        cpu_now = task.ps_proc.cpu_percent(None)
                        rss_now = task.ps_proc.memory_info().rss
                        task.peak_cpu_percent = max(task.peak_cpu_percent, cpu_now)
                        task.peak_rss_bytes = max(task.peak_rss_bytes, rss_now)
                    except Exception:
                        pass
            elif task.status == "Queued":
                queued += 1

        self.metrics_app_cpu.setText(f"{app_cpu:.1f}%")
        self.metrics_app_ram.setText(_format_bytes(app_ram))
        self.metrics_sys_cpu.setText(f"{sys_cpu:.1f}%")
        self.metrics_sys_ram.setText(f"{sys_ram:.1f}%")
        gpu_stats = self._query_nvidia_gpu_metrics()
        if gpu_stats is None:
            self.metrics_gpu.setText("N/A")
            self.metrics_gpu_vram.setText("N/A")
        else:
            gpu_util, used_mib, total_mib, gpu_count = gpu_stats
            used_bytes = used_mib * 1024 * 1024
            total_bytes = total_mib * 1024 * 1024
            suffix = f" ({gpu_count} GPUs)" if gpu_count > 1 else ""
            self.metrics_gpu.setText(f"{gpu_util:.0f}%{suffix}")
            self.metrics_gpu_vram.setText(f"{_format_bytes(used_bytes)} / {_format_bytes(total_bytes)}")
        cpu_state, cpu_color = self._resource_health(sys_cpu, 60.0, 85.0)
        ram_state, ram_color = self._resource_health(sys_ram, 70.0, 88.0)
        self.metrics_cpu_health.setText(cpu_state)
        self.metrics_cpu_health.setStyleSheet(f"color: {cpu_color}; font-weight: 700;")
        self.metrics_ram_health.setText(ram_state)
        self.metrics_ram_health.setStyleSheet(f"color: {ram_color}; font-weight: 700;")
        self.metrics_workers.setText(f"{running} active / {queued} queued")

    def _append_metrics_to_log(self, task: TaskItem) -> None:
        if not task.log_file:
            return
        if not task.log_file.exists():
            return
        metrics = task.metrics
        lines = [
            "",
            "=== GUI Summary ===",
            f"Peak child CPU% observed by GUI: {task.peak_cpu_percent:.2f}",
            f"Peak child RSS observed by GUI: {task.peak_rss_bytes} bytes ({_format_bytes(task.peak_rss_bytes)})",
            f"Duration (reported): {metrics.get('duration_seconds', 0.0):.2f} seconds",
            f"Input size: {metrics.get('input_size', 0)} bytes ({_format_bytes(int(metrics.get('input_size', 0)))})",
            f"Output size: {metrics.get('output_size', 0)} bytes ({_format_bytes(int(metrics.get('output_size', 0)))})",
            f"Output/Input ratio: {float(metrics.get('size_ratio', 0.0)):.4f}",
            f"CPU user delta: {float(metrics.get('cpu_user_delta', 0.0)):.4f}",
            f"CPU system delta: {float(metrics.get('cpu_system_delta', 0.0)):.4f}",
        ]
        try:
            with task.log_file.open("a", encoding="utf-8") as handle:
                handle.write("\n".join(lines) + "\n")
        except Exception:
            pass

    def _append_cancel_to_log(self, task: TaskItem) -> None:
        if not task.log_file:
            return
        try:
            task.log_file.parent.mkdir(parents=True, exist_ok=True)
            with task.log_file.open("a", encoding="utf-8") as handle:
                handle.write("\n=== GUI Summary ===\nCanceled by user.\n")
                handle.write(f"Peak child CPU% observed by GUI: {task.peak_cpu_percent:.2f}\n")
                handle.write(
                    f"Peak child RSS observed by GUI: {task.peak_rss_bytes} bytes ({_format_bytes(task.peak_rss_bytes)})\n"
                )
        except Exception:
            pass

    def open_log_folder(self) -> None:
        target = self.batch_log_dir if self.batch_log_dir and self.batch_log_dir.exists() else LOG_ROOT
        target.mkdir(parents=True, exist_ok=True)
        opened = self._open_in_file_manager(target)
        if not opened:
            opened = self._open_with_system_default(target)
        if not opened:
            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        if not opened:
            QMessageBox.warning(self, "Open Log Folder", f"Could not open {target}")

    def _state_file_path(self) -> Path:
        config_dir = QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
        if not config_dir:
            return LOG_ROOT / "queue_state.json"
        return Path(config_dir) / "queue_state.json"

    @staticmethod
    def _is_secure_state_file(path: Path) -> bool:
        if not path.exists():
            return True
        if path.is_symlink():
            return False
        if os.name == "nt":
            return True
        try:
            mode = path.stat().st_mode
        except Exception:
            return False
        return (mode & (stat.S_IWGRP | stat.S_IWOTH)) == 0

    def _save_queue_state(self) -> None:
        queued_paths = [
            str(task.input_path)
            for task in self.tasks.values()
            if task.status in {"Queued", "Running", "Canceling..."}
        ]
        state_file = self._state_file_path()
        state_file.parent.mkdir(parents=True, exist_ok=True)
        if state_file.exists() and not self._is_secure_state_file(state_file):
            return
        if not queued_paths:
            if state_file.exists():
                try:
                    state_file.unlink()
                except Exception:
                    pass
            return
        payload = {
            "version": 1,
            "queued_paths": queued_paths,
            "ocr_mode": self.ocr_mode.currentData() if hasattr(self, "ocr_mode") else "smart",
            "use_gpu_acceleration": self.gpu_checkbox.isChecked() if hasattr(self, "gpu_checkbox") else False,
            "optimize_for_size": self.optimize_size_checkbox.isChecked() if hasattr(self, "optimize_size_checkbox") else False,
            "parallel_mode": self.parallel_mode.currentData() if hasattr(self, "parallel_mode") else "auto",
            "custom_workers": self.custom_workers.value() if hasattr(self, "custom_workers") else DEFAULT_WORKERS,
            "priority_mode": self.priority_combo.currentData() if hasattr(self, "priority_combo") else "normal",
            "path_display_mode": self.path_display_combo.currentData() if hasattr(self, "path_display_combo") else "elided",
            "file_manager_choice": self.file_manager_choice if self.file_manager_choice != "custom" else "auto",
        }
        tmp_file = state_file.with_suffix(".tmp")
        try:
            tmp_file.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
            if os.name != "nt":
                os.chmod(tmp_file, 0o600)
            tmp_file.replace(state_file)
            if os.name != "nt":
                os.chmod(state_file, 0o600)
        except Exception:
            try:
                if tmp_file.exists():
                    tmp_file.unlink()
            except Exception:
                pass
            return

    def _restore_queue_state_prompt(self) -> None:
        state_file = self._state_file_path()
        if not state_file.exists():
            return
        if not self._is_secure_state_file(state_file):
            self._append_log("Skipped restoring queue state due to unsafe state-file permissions.")
            return
        try:
            if state_file.stat().st_size > MAX_STATE_FILE_BYTES:
                self._append_log("Skipped restoring queue state because state file is too large.")
                return
        except Exception:
            return
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(data, dict):
            return
        queued_raw = data.get("queued_paths", [])
        if not isinstance(queued_raw, list):
            return
        queued_paths: list[str] = []
        seen: set[str] = set()
        restore_cap = min(MAX_RESTORE_PATHS, MAX_QUEUE_ITEMS)
        for raw_path in queued_raw[:restore_cap]:
            try:
                candidate = Path(str(raw_path)).expanduser().resolve()
            except Exception:
                continue
            if not candidate.exists() or not candidate.is_file() or candidate.suffix.lower() != ".pdf":
                continue
            key = str(candidate)
            if key in seen:
                continue
            seen.add(key)
            queued_paths.append(key)
        if not queued_paths:
            return

        answer = QMessageBox.question(
            self,
            "Restore Queue",
            f"Found {len(queued_paths)} queued file(s) from last session. Restore them?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            try:
                state_file.unlink()
            except Exception:
                pass
            return

        self._set_combo_data(self.ocr_mode, str(data.get("ocr_mode", self.ocr_mode.currentData())))
        self.gpu_checkbox.setChecked(bool(data.get("use_gpu_acceleration", self.gpu_checkbox.isChecked())))
        self.optimize_size_checkbox.setChecked(bool(data.get("optimize_for_size", self.optimize_size_checkbox.isChecked())))
        self._set_combo_data(self.parallel_mode, str(data.get("parallel_mode", self.parallel_mode.currentData())))
        try:
            restored_workers = int(data.get("custom_workers", self.custom_workers.value()))
        except Exception:
            restored_workers = self.custom_workers.value()
        self.custom_workers.setValue(max(1, min(MAX_WORKERS, restored_workers)))
        self._set_combo_data(self.priority_combo, str(data.get("priority_mode", self.priority_combo.currentData())))
        self._set_combo_data(
            self.path_display_combo,
            str(data.get("path_display_mode", self.path_display_combo.currentData())),
        )
        self.file_manager_choice = str(data.get("file_manager_choice", self.file_manager_choice))
        valid_choices = {manager_id for manager_id, _label, _cmd in self._file_manager_options_for_platform()}
        valid_choices.add("custom")
        if self.file_manager_choice not in valid_choices:
            self.file_manager_choice = "auto"
        if self.file_manager_choice == "custom":
            self.file_manager_choice = "auto"
        self._refresh_file_manager_actions()

        self.add_paths(queued_paths)
        self._append_log(f"Restored {len(queued_paths)} queued item(s) from previous session.")

    def show_usage(self) -> None:
        QMessageBox.information(
            self,
            "Usage",
            "1) Drag PDFs/folders or use Add buttons.\n"
            "2) Optional: open Advanced to tune GPU, output size, parallel files, and priority.\n"
            "3) Click Start OCR.\n"
            "4) Cancel Selected/All to stop active jobs immediately.\n"
            "5) Output PDFs are written to OCR_Output next to originals.\n"
            "6) Per-file logs are saved under logs/<batch>/.",
        )

    def show_about(self) -> None:
        QMessageBox.information(
            self,
            "About",
            f"{APP_NAME}\n\n"
            "Cross-platform batch OCR desktop app built with PySide6.\n\n"
            "Highlights:\n"
            "- Drag-and-drop PDF/folder queue\n"
            "- Parallel OCR execution with live logs\n"
            "- Per-file cancel/open-log controls\n"
            "- Runtime CPU/RAM health indicators (+ NVIDIA GPU/VRAM when available)\n\n"
            "Powered by OCRmyPDF, Tesseract, Ghostscript, and qpdf.",
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        running = [task for task in self.tasks.values() if task.status == "Running"]
        if running:
            answer = QMessageBox.question(
                self,
                "Exit",
                "There are OCR jobs running. Cancel all and exit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self.cancel_all()
        self.settings.setValue("last_dir", self.last_dir)
        self.settings.setValue("theme", self.theme)
        self.settings.setValue("parallel_mode", self.parallel_mode.currentData())
        self.settings.setValue("custom_workers", self.custom_workers.value())
        self.settings.setValue("ocr_mode", self.ocr_mode.currentData())
        self.settings.setValue("use_gpu_acceleration", self.gpu_checkbox.isChecked())
        self.settings.setValue("optimize_for_size", self.optimize_size_checkbox.isChecked())
        self.settings.setValue("priority_mode", self.priority_combo.currentData())
        self.settings.setValue("path_display_mode", self.path_display_combo.currentData())
        self.settings.setValue("show_stats", self.show_stats_toggle.isChecked())
        self.settings.setValue("file_manager_choice", self.file_manager_choice)
        self.settings.setValue("file_manager_custom_cmd", self.file_manager_custom_cmd)
        self._save_queue_state()
        super().closeEvent(event)

    def _append_log(self, message: str, task_id: str | None = None) -> None:
        if not message:
            return
        level = self._extract_log_level(message)
        self.log_entries.append((task_id, level, message))
        if len(self.log_entries) > 20000:
            self.log_entries = self.log_entries[-20000:]
        if self._log_entry_visible(task_id, level):
            self.log_view.appendPlainText(message)
            scroll = self.log_view.verticalScrollBar()
            scroll.setValue(scroll.maximum())

    def _extract_log_level(self, message: str) -> str:
        parts = message.split(" | ")
        if len(parts) >= 3:
            candidate = parts[1].strip().upper()
            if candidate in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
                return candidate
        return "INFO"

    def _log_entry_visible(self, task_id: str | None, level: str) -> bool:
        level_mode = self.log_level_combo.currentData() if hasattr(self, "log_level_combo") else "all"
        if level_mode == "warning" and level not in {"WARNING", "ERROR", "CRITICAL"}:
            return False
        if level_mode == "error" and level not in {"ERROR", "CRITICAL"}:
            return False

        mode = self.log_filter_combo.currentData() if hasattr(self, "log_filter_combo") else "all"
        if mode != "selected":
            return True
        selected = self._current_selected_task_id()
        if selected is None:
            return False
        return task_id == selected

    def _current_selected_task_id(self) -> str | None:
        selected = self._selected_task_ids()
        if not selected:
            return None
        return selected[0]

    def _refresh_log_view(self) -> None:
        self.log_view.clear()
        for task_id, level, message in self.log_entries:
            if self._log_entry_visible(task_id, level):
                self.log_view.appendPlainText(message)
        scroll = self.log_view.verticalScrollBar()
        scroll.setValue(scroll.maximum())

    @staticmethod
    def _next_output_path(target_dir: Path, stem: str) -> Path:
        if target_dir.exists() and target_dir.is_symlink():
            raise RuntimeError(f"Refusing symlink output directory: {target_dir}")
        target_dir.mkdir(parents=True, exist_ok=True)
        if target_dir.is_symlink():
            raise RuntimeError(f"Refusing symlink output directory: {target_dir}")

        candidate = target_dir / f"{stem}.pdf"
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
        idx = 2
        while idx <= 100000:
            alt = target_dir / f"{stem}_{idx}.pdf"
            if not alt.exists() and not alt.is_symlink():
                return alt
            idx += 1
        raise RuntimeError("Could not allocate safe output filename.")


def run_app() -> int:
    _set_windows_app_user_model_id()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    if hasattr(app, "setDesktopFileName") and _linux_desktop_entry_available("ocr_gui"):
        app.setDesktopFileName("ocr_gui")
    app_icon = None
    icon_path = _resolve_app_icon_path()
    if icon_path is not None:
        app_icon = QIcon(str(icon_path))
        if not app_icon.isNull():
            app.setWindowIcon(app_icon)
    window = MainWindow(app)
    if app_icon is not None and not app_icon.isNull():
        window.setWindowIcon(app_icon)
    window.show()
    return app.exec()
