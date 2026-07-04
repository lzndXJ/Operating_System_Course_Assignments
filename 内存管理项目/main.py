"""PyQt5 GUI for a dynamic partition memory management simulator."""

import re
import sys
from datetime import datetime
from typing import Dict, List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from memory_bar import MemoryBar
from memory_manager import MemoryManager, OperationResult


class MainWindow(QMainWindow):
    DEFAULT_MEMORY_SIZE = 640
    EXAMPLE_TASKS = [
        {"type": "alloc", "size": 130},
        {"type": "alloc", "size": 60},
        {"type": "alloc", "size": 100},
        {"type": "release", "job_no": 2},
        {"type": "alloc", "size": 200},
        {"type": "alloc", "size": 140},
        {"type": "release", "job_no": 1},
        {"type": "alloc", "size": 50},
        {"type": "alloc", "size": 60},
        {"type": "release", "job_no": 3},
        {"type": "alloc", "size": 80},
        {"type": "release", "job_no": 7},
        {"type": "release", "job_no": 6},
        {"type": "alloc", "size": 80},
    ]

    def __init__(self) -> None:
        # 初始化主窗口状态和界面。
        super().__init__()
        self.ff_manager = MemoryManager(self.DEFAULT_MEMORY_SIZE, "FF")
        self.bf_manager = MemoryManager(self.DEFAULT_MEMORY_SIZE, "BF")
        self.next_job_id = 1
        self.example_tasks: List[Dict[str, int]] = []
        self.example_index = 0
        self.example_alloc_count = 0
        self.example_job_map: Dict[int, str] = {}

        self.setWindowTitle("动态分区存储管理模拟系统")
        self.resize(1280, 860)
        self._build_ui()
        self._apply_style()
        self.refresh_all()
        self._update_example_status()

    def _build_ui(self) -> None:
        # 创建主窗口的全部界面控件。
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 10, 12, 10)
        root_layout.setSpacing(8)

        title = QLabel("动态分区存储管理模拟系统")
        title.setAlignment(Qt.AlignCenter)
        title.setObjectName("titleLabel")
        root_layout.addWidget(title)

        control_box = QGroupBox("操作控制")
        control_layout = QGridLayout(control_box)
        control_layout.setHorizontalSpacing(10)
        control_layout.setVerticalSpacing(8)

        self.total_input = QLineEdit(str(self.DEFAULT_MEMORY_SIZE))
        self.total_input.setValidator(QIntValidator(1, 10_000_000, self))
        self.total_input.setFixedWidth(92)
        self.reset_button = QPushButton("初始化 / 重置内存")
        self.reset_button.clicked.connect(self.reset_memory)

        self.request_input = QLineEdit()
        self.request_input.setValidator(QIntValidator(1, 10_000_000, self))
        self.request_input.setPlaceholderText("如 130")
        self.request_input.setFixedWidth(92)
        self.allocate_button = QPushButton("申请内存")
        self.allocate_button.clicked.connect(self.allocate_from_input)

        self.release_combo = QComboBox()
        self.release_combo.setMinimumWidth(140)
        self.release_button = QPushButton("释放选中作业")
        self.release_button.clicked.connect(self.release_selected_job)

        self.load_example_button = QPushButton("加载示例任务序列")
        self.load_example_button.clicked.connect(self.load_example_tasks)
        self.step_button = QPushButton("单步执行")
        self.step_button.clicked.connect(self.execute_example_step)
        self.run_all_button = QPushButton("一键执行全部")
        self.run_all_button.clicked.connect(self.execute_all_examples)

        control_layout.addWidget(QLabel("总内存(K)："), 0, 0)
        control_layout.addWidget(self.total_input, 0, 1)
        control_layout.addWidget(self.reset_button, 0, 2)
        control_layout.addWidget(QLabel("申请大小(K)："), 0, 3)
        control_layout.addWidget(self.request_input, 0, 4)
        control_layout.addWidget(self.allocate_button, 0, 5)
        control_layout.addWidget(QLabel("释放作业："), 0, 6)
        control_layout.addWidget(self.release_combo, 0, 7)
        control_layout.addWidget(self.release_button, 0, 8)
        control_layout.addWidget(self.load_example_button, 1, 2)
        control_layout.addWidget(self.step_button, 1, 3)
        control_layout.addWidget(self.run_all_button, 1, 4)
        control_layout.setColumnStretch(9, 1)

        root_layout.addWidget(control_box)

        self.algorithm_splitter = QSplitter(Qt.Horizontal)
        ff_panel, self.ff_widgets = self._create_algorithm_panel("首次适应算法 FF")
        bf_panel, self.bf_widgets = self._create_algorithm_panel("最佳适应算法 BF")
        self.algorithm_splitter.addWidget(ff_panel)
        self.algorithm_splitter.addWidget(bf_panel)
        self.algorithm_splitter.setSizes([640, 640])
        root_layout.addWidget(self.algorithm_splitter, 1)

        bottom_frame = QFrame()
        bottom_frame.setObjectName("bottomFrame")
        bottom_layout = QHBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(10, 8, 10, 8)
        self.example_progress_label = QLabel()
        self.pending_task_label = QLabel()
        self.status_label = QLabel("就绪。")
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bottom_layout.addWidget(self.example_progress_label)
        bottom_layout.addWidget(self.pending_task_label, 1)
        bottom_layout.addWidget(self.status_label, 1)
        root_layout.addWidget(bottom_frame)

        self.ff_widgets["allocated_table"].cellClicked.connect(
            lambda row, column: self._select_job_from_table(self.ff_widgets["allocated_table"], row)
        )
        self.bf_widgets["allocated_table"].cellClicked.connect(
            lambda row, column: self._select_job_from_table(self.bf_widgets["allocated_table"], row)
        )

    def _create_algorithm_panel(self, title: str):
        # 创建单个算法展示面板。
        panel = QGroupBox(title)
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)

        memory_bar = MemoryBar()
        layout.addWidget(memory_bar)

        table_layout = QHBoxLayout()
        free_block = QWidget()
        free_layout = QVBoxLayout(free_block)
        free_layout.setContentsMargins(0, 0, 0, 0)
        free_label = QLabel("空闲分区表")
        free_table = self._create_table(["序号", "起始地址", "分区大小", "结束地址"])
        free_layout.addWidget(free_label)
        free_layout.addWidget(free_table)

        allocated_block = QWidget()
        allocated_layout = QVBoxLayout(allocated_block)
        allocated_layout.setContentsMargins(0, 0, 0, 0)
        allocated_label = QLabel("已分配分区表")
        allocated_table = self._create_table(["作业名", "起始地址", "分区大小", "结束地址"])
        allocated_layout.addWidget(allocated_label)
        allocated_layout.addWidget(allocated_table)

        table_layout.addWidget(free_block)
        table_layout.addWidget(allocated_block)
        layout.addLayout(table_layout, 1)

        log_label = QLabel("操作日志")
        log_edit = QTextEdit()
        log_edit.setReadOnly(True)
        log_edit.setMinimumHeight(150)
        log_edit.setLineWrapMode(QTextEdit.WidgetWidth)
        layout.addWidget(log_label)
        layout.addWidget(log_edit)

        return panel, {
            "bar": memory_bar,
            "free_table": free_table,
            "allocated_table": allocated_table,
            "log": log_edit,
        }

    def _create_table(self, headers: List[str]) -> QTableWidget:
        # 创建统一样式的数据表格。
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setMinimumHeight(190)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        return table

    def _apply_style(self) -> None:
        # 设置窗口和控件的样式表。
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f5f7fb;
            }
            QLabel#titleLabel {
                color: #0f172a;
                font-size: 24px;
                font-weight: 700;
                padding: 4px 0 8px 0;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #d7dde8;
                border-radius: 6px;
                margin-top: 10px;
                padding: 8px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #334155;
            }
            QLineEdit, QComboBox {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                min-height: 28px;
                padding: 2px 6px;
            }
            QPushButton {
                background: #2563eb;
                color: white;
                border: 1px solid #1d4ed8;
                border-radius: 4px;
                min-height: 28px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background: #1d4ed8;
            }
            QPushButton:pressed {
                background: #1e40af;
            }
            QTableWidget {
                background: #ffffff;
                alternate-background-color: #f8fafc;
                border: 1px solid #d7dde8;
                gridline-color: #e2e8f0;
            }
            QHeaderView::section {
                background: #eef2f7;
                color: #334155;
                border: 0;
                border-right: 1px solid #d7dde8;
                border-bottom: 1px solid #d7dde8;
                padding: 5px;
                font-weight: 600;
            }
            QTextEdit {
                background: #0f172a;
                color: #e5e7eb;
                border: 1px solid #1e293b;
                border-radius: 4px;
                padding: 6px;
                font-family: Consolas, "Microsoft YaHei";
            }
            QFrame#bottomFrame {
                background: #ffffff;
                border: 1px solid #d7dde8;
                border-radius: 6px;
            }
            """
        )

    def reset_memory(self) -> None:
        # 根据输入总内存重置系统状态。
        total_size = self._read_positive_int(self.total_input, "总内存")
        if total_size is None:
            return

        self.ff_manager.reset(total_size)
        self.bf_manager.reset(total_size)
        self.next_job_id = 1
        self.example_tasks = []
        self.example_index = 0
        self.example_alloc_count = 0
        self.example_job_map = {}
        self.ff_widgets["log"].clear()
        self.bf_widgets["log"].clear()
        self.refresh_all()
        self._update_example_status()
        self.status_label.setText(f"已初始化：总内存 {total_size}K，作业编号从 1 开始。")

    def allocate_from_input(self) -> None:
        # 读取输入大小并执行手动申请。
        request_size = self._read_positive_int(self.request_input, "申请大小")
        if request_size is None:
            return
        self._execute_allocate(request_size, "手动操作")
        self.request_input.clear()

    def release_selected_job(self) -> None:
        # 释放下拉框中选中的作业。
        job_name = self.release_combo.currentData()
        if not job_name:
            self._show_warning("请选择需要释放的作业。")
            return
        self._execute_release(str(job_name), "手动操作", show_warning=True)

    def load_example_tasks(self) -> None:
        # 加载内置示例任务序列。
        self.example_tasks = [dict(task) for task in self.EXAMPLE_TASKS]
        self.example_index = 0
        self.example_alloc_count = 0
        self.example_job_map = {}
        self._update_example_status()
        self.status_label.setText("示例任务序列已加载，等待执行。")

    def execute_example_step(self) -> None:
        # 单步执行一条示例任务。
        if not self.example_tasks:
            self._show_warning("示例任务序列没有加载，请先点击“加载示例任务序列”。")
            return
        if self.example_index >= len(self.example_tasks):
            self._show_warning("示例任务已经全部执行完毕。")
            return
        self._execute_current_example_task()

    def execute_all_examples(self) -> None:
        # 连续执行剩余全部示例任务。
        if not self.example_tasks:
            self._show_warning("示例任务序列没有加载，请先点击“加载示例任务序列”。")
            return
        if self.example_index >= len(self.example_tasks):
            self._show_warning("示例任务已经全部执行完毕。")
            return

        while self.example_index < len(self.example_tasks):
            self._execute_current_example_task()
            QApplication.processEvents()
        self.status_label.setText("示例任务序列已全部执行完成。")

    def _execute_current_example_task(self) -> None:
        # 执行当前索引指向的示例任务。
        task = self.example_tasks[self.example_index]
        step_no = self.example_index + 1
        if task["type"] == "alloc":
            job_name = self._execute_allocate(int(task["size"]), f"示例第 {step_no} 步")
            if job_name:
                self.example_alloc_count += 1
                self.example_job_map[self.example_alloc_count] = job_name
        else:
            relative_no = int(task["job_no"])
            job_name = self.example_job_map.get(relative_no, f"作业{relative_no}")
            self._execute_release(job_name, f"示例第 {step_no} 步")

        self.example_index += 1
        self._update_example_status()

    def _execute_allocate(self, request_size: int, source: str) -> Optional[str]:
        # 同时在 FF 和 BF 中执行申请操作。
        total_size = self.ff_manager.total_size
        if request_size > total_size:
            self._show_warning(f"申请大小 {request_size}K 大于总内存 {total_size}K。")
            return None

        job_name = f"作业{self.next_job_id}"
        self.next_job_id += 1
        operation_text = f"{source}：{job_name} 申请 {request_size}K"

        ff_result = self.ff_manager.allocate(job_name, request_size)
        bf_result = self.bf_manager.allocate(job_name, request_size)
        self._log_result(self.ff_widgets["log"], operation_text, ff_result)
        self._log_result(self.bf_widgets["log"], operation_text, bf_result)

        self.refresh_all()
        self.status_label.setText(f"{operation_text} 已执行。")
        return job_name

    def _execute_release(self, job_name: str, source: str, show_warning: bool = False) -> None:
        # 同时在 FF 和 BF 中执行释放操作。
        operation_text = f"{source}：释放 {job_name}"
        ff_result = self.ff_manager.release(job_name)
        bf_result = self.bf_manager.release(job_name)
        self._log_result(self.ff_widgets["log"], operation_text, ff_result)
        self._log_result(self.bf_widgets["log"], operation_text, bf_result)

        self.refresh_all()
        if show_warning and not ff_result.success and not bf_result.success:
            self._show_warning(f"{job_name} 在 FF 和 BF 中都不存在或已经释放。")
        else:
            self.status_label.setText(f"{operation_text} 已执行。")

    def _log_result(self, log_edit: QTextEdit, operation_text: str, result: OperationResult) -> None:
        # 将一次操作结果写入日志框。
        now = datetime.now().strftime("%H:%M:%S")
        log_edit.append(f"[{now}] 执行：{operation_text}")
        log_edit.append(f"  {result.message}")
        if result.success and result.start is not None and result.size is not None:
            if "释放" in operation_text:
                if result.merged:
                    log_edit.append(f"  空闲区发生合并：{result.merge_message}")
                else:
                    log_edit.append("  空闲区没有发生合并。")
        log_edit.append("")

    def refresh_all(self) -> None:
        # 刷新内存条、表格和释放作业列表。
        self.ff_widgets["bar"].set_manager(self.ff_manager)
        self.bf_widgets["bar"].set_manager(self.bf_manager)
        self._fill_free_table(self.ff_widgets["free_table"], self.ff_manager.get_free_table())
        self._fill_free_table(self.bf_widgets["free_table"], self.bf_manager.get_free_table())
        self._fill_allocated_table(self.ff_widgets["allocated_table"], self.ff_manager.get_allocated_table())
        self._fill_allocated_table(self.bf_widgets["allocated_table"], self.bf_manager.get_allocated_table())
        self._refresh_release_combo()

    def _fill_free_table(self, table: QTableWidget, rows: List[Dict[str, int]]) -> None:
        # 填充空闲分区表。
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [row["index"], f'{row["start"]}K', f'{row["size"]}K', f'{row["end"]}K']
            self._set_table_row(table, row_index, values)

    def _fill_allocated_table(self, table: QTableWidget, rows: List[Dict[str, int]]) -> None:
        # 填充已分配分区表。
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [row["job_name"], f'{row["start"]}K', f'{row["size"]}K', f'{row["end"]}K']
            self._set_table_row(table, row_index, values)

    def _set_table_row(self, table: QTableWidget, row_index: int, values: List[object]) -> None:
        # 设置表格中一整行的显示内容。
        for column_index, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row_index, column_index, item)

    def _refresh_release_combo(self) -> None:
        # 根据当前已分配作业刷新释放下拉框。
        current = self.release_combo.currentData()
        jobs = {
            row["job_name"]
            for row in self.ff_manager.get_allocated_table() + self.bf_manager.get_allocated_table()
        }
        sorted_jobs = sorted(jobs, key=self._job_sort_key)

        self.release_combo.blockSignals(True)
        self.release_combo.clear()
        self.release_combo.addItem("请选择作业", None)
        for job_name in sorted_jobs:
            self.release_combo.addItem(job_name, job_name)
        if current in jobs:
            self.release_combo.setCurrentIndex(self.release_combo.findData(current))
        self.release_combo.blockSignals(False)

    def _select_job_from_table(self, table: QTableWidget, row: int) -> None:
        # 点击表格行时同步选中释放作业。
        item = table.item(row, 0)
        if item is None:
            return
        index = self.release_combo.findData(item.text())
        if index >= 0:
            self.release_combo.setCurrentIndex(index)

    def _update_example_status(self) -> None:
        # 更新示例任务进度和待执行提示。
        if not self.example_tasks:
            self.example_progress_label.setText("示例任务：未加载")
            self.pending_task_label.setText("当前待执行：无")
            return

        total = len(self.example_tasks)
        self.example_progress_label.setText(f"示例任务进度：{self.example_index}/{total}")
        if self.example_index >= total:
            self.pending_task_label.setText("当前待执行：已全部完成")
        else:
            task_text = self._format_example_task(self.example_tasks[self.example_index])
            self.pending_task_label.setText(f"当前待执行：第 {self.example_index + 1} 步 - {task_text}")

    def _format_example_task(self, task: Dict[str, int]) -> str:
        # 将示例任务转换为界面提示文字。
        if task["type"] == "alloc":
            return f"申请 {task['size']}K"
        relative_no = int(task["job_no"])
        job_name = self.example_job_map.get(relative_no)
        if job_name:
            return f"释放 {job_name}"
        return f"释放 作业{relative_no}"

    def _read_positive_int(self, line_edit: QLineEdit, field_name: str) -> Optional[int]:
        # 校验输入框中的正整数。
        text = line_edit.text().strip()
        if not text:
            self._show_warning(f"{field_name}不能为空。")
            return None
        try:
            value = int(text)
        except ValueError:
            self._show_warning(f"{field_name}必须是正整数。")
            return None
        if value <= 0:
            self._show_warning(f"{field_name}必须是正整数。")
            return None
        return value

    def _show_warning(self, message: str) -> None:
        # 显示警告弹窗并更新状态栏。
        self.status_label.setText(message)
        QMessageBox.warning(self, "提示", message)

    def _job_sort_key(self, job_name: str):
        # 按作业编号对作业名排序。
        match = re.search(r"\d+", job_name)
        if match:
            return int(match.group(0))
        return job_name


def main() -> None:
    # 创建应用并启动主事件循环。
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
