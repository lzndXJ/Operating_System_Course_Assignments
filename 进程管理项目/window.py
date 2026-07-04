"""PyQt5 主窗口界面。"""

from __future__ import annotations

from functools import partial
from typing import Dict, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLCDNumber,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import ELEVATOR_COUNT, FLOOR_COUNT, MAX_FLOOR, MIN_FLOOR
from elevator import Direction, ElevatorThread
from scheduler import ElevatorScheduler


class MainWindow(QMainWindow):
    # 初始化主窗口：创建电梯线程、调度器、界面控件字典，并启动所有电梯线程。
    def __init__(self):
        super().__init__()
        self.setWindowTitle("五电梯调度模拟系统")
        self.resize(1380, 820)

        self.elevators = [ElevatorThread(index + 1, self) for index in range(ELEVATOR_COUNT)]
        self.scheduler = ElevatorScheduler(self.elevators, self)

        self.floor_lcds: Dict[int, QLCDNumber] = {}
        self.status_labels: Dict[int, QLabel] = {}
        self.pause_buttons: Dict[int, QPushButton] = {}
        self.internal_buttons: Dict[Tuple[int, int], QPushButton] = {}
        self.external_buttons: Dict[Tuple[int, Direction], QPushButton] = {}

        self._build_ui()
        self._connect_signals()
        self._apply_styles()

        for elevator in self.elevators:
            elevator.start()

    # 窗口关闭事件：通知所有电梯线程停止，并等待线程退出，防止程序残留后台线程。
    def closeEvent(self, event):
        for elevator in self.elevators:
            elevator.stop()
        for elevator in self.elevators:
            elevator.wait(1500)
        event.accept()

    # 构建主界面整体布局，包括标题、电梯区域、外部请求区域和运行日志区域。
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title = QLabel("五电梯调度模拟系统")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_elevator_area())
        splitter.addWidget(self._build_external_panel())
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([1500, 280])
        root.addWidget(splitter, 1)

        log_box = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_box)
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMinimumHeight(145)
        log_layout.addWidget(self.log_edit)
        root.addWidget(log_box)

        self.setCentralWidget(central)

    # 构建左侧五部电梯的显示区域，每部电梯占一列。
    def _build_elevator_area(self) -> QWidget:
        area = QWidget()
        layout = QHBoxLayout(area)
        layout.setSpacing(10)

        for elevator_id in range(1, ELEVATOR_COUNT + 1):
            layout.addWidget(self._build_elevator_box(elevator_id))
        return area

    # 构建单部电梯的界面，包括 LCD 楼层显示、状态显示、暂停按钮和内部楼层按钮。
    def _build_elevator_box(self, elevator_id: int) -> QGroupBox:
        box = QGroupBox(f"电梯 {elevator_id}")
        layout = QVBoxLayout(box)
        layout.setSpacing(8)

        lcd = QLCDNumber()
        lcd.setDigitCount(2)
        lcd.display(MIN_FLOOR)
        self.floor_lcds[elevator_id] = lcd
        layout.addWidget(lcd)

        status = QLabel("静止")
        status.setAlignment(Qt.AlignCenter)
        status.setObjectName("StatusLabel")
        self.status_labels[elevator_id] = status
        layout.addWidget(status)

        pause = QPushButton("暂停")
        pause.setCheckable(True)
        pause.clicked.connect(partial(self._toggle_pause, elevator_id))
        self.pause_buttons[elevator_id] = pause
        layout.addWidget(pause)

        button_grid = QGridLayout()
        button_grid.setSpacing(5)
        for floor in range(MAX_FLOOR, MIN_FLOOR - 1, -1):
            button = QPushButton(str(floor))
            button.setFixedHeight(30)
            button.clicked.connect(partial(self._request_internal, elevator_id, floor))
            self.internal_buttons[(elevator_id, floor)] = button
            row = MAX_FLOOR - floor
            button_grid.addWidget(button, row // 4, row % 4)
        layout.addLayout(button_grid)
        return box

    # 构建右侧楼层外部请求面板，包括每层楼的上行和下行按钮。
    def _build_external_panel(self) -> QGroupBox:
        box = QGroupBox("楼层外部请求")
        box.setMinimumWidth(240)
        outer_layout = QVBoxLayout(box)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        content.setMinimumWidth(190)
        grid = QGridLayout(content)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(5)

        grid.addWidget(QLabel("楼层"), 0, 0, alignment=Qt.AlignCenter)
        grid.addWidget(QLabel("上行"), 0, 1, alignment=Qt.AlignCenter)
        grid.addWidget(QLabel("下行"), 0, 2, alignment=Qt.AlignCenter)
        grid.setColumnMinimumWidth(0, 54)
        grid.setColumnMinimumWidth(1, 54)
        grid.setColumnMinimumWidth(2, 54)

        for visual_row, floor in enumerate(range(MAX_FLOOR, MIN_FLOOR - 1, -1), start=1):
            floor_label = QLabel(f"{floor}F")
            floor_label.setAlignment(Qt.AlignCenter)
            grid.addWidget(floor_label, visual_row, 0)

            up_button = QPushButton("▲")
            down_button = QPushButton("▼")
            up_button.setMinimumWidth(46)
            down_button.setMinimumWidth(46)
            up_button.setToolTip(f"{floor}楼上行请求")
            down_button.setToolTip(f"{floor}楼下行请求")
            up_button.clicked.connect(partial(self._request_external, floor, "up"))
            down_button.clicked.connect(partial(self._request_external, floor, "down"))

            if floor == MAX_FLOOR:
                up_button.setEnabled(False)
            if floor == MIN_FLOOR:
                down_button.setEnabled(False)

            self.external_buttons[(floor, "up")] = up_button
            self.external_buttons[(floor, "down")] = down_button
            grid.addWidget(up_button, visual_row, 1)
            grid.addWidget(down_button, visual_row, 2)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)
        return box

    # 连接调度器和电梯线程的信号到主窗口槽函数，保证 GUI 更新都在主线程执行。
    def _connect_signals(self) -> None:
        self.scheduler.log_message.connect(self._append_log)
        for elevator in self.elevators:
            elevator.state_changed.connect(self._update_elevator_state)
            elevator.log_message.connect(self._append_log)
            elevator.request_served.connect(self._handle_request_served)

    # 处理电梯内部按钮点击：改变按钮颜色，并把目标楼层加入对应电梯的目标队列。
    def _request_internal(self, elevator_id: int, floor: int) -> None:
        button = self.internal_buttons[(elevator_id, floor)]
        button.setProperty("active", True)
        button.style().unpolish(button)
        button.style().polish(button)
        self.elevators[elevator_id - 1].add_internal_target(floor)

    # 处理楼层外部按钮点击：登记请求、改变按钮颜色，并交给调度器选择电梯。
    def _request_external(self, floor: int, direction: Direction) -> None:
        button = self.external_buttons[(floor, direction)]
        if not button.isEnabled():
            return
        button.setProperty("active", True)
        button.setEnabled(False)
        button.style().unpolish(button)
        button.style().polish(button)
        self.scheduler.dispatch_external_request(floor, direction)

    # 处理暂停/启动按钮点击：切换按钮文字，并通知对应电梯线程暂停或继续。
    def _toggle_pause(self, elevator_id: int, checked: bool) -> None:
        button = self.pause_buttons[elevator_id]
        button.setText("启动" if checked else "暂停")
        self.elevators[elevator_id - 1].set_paused(checked)

    # 接收电梯状态信号，更新对应电梯的 LCD 楼层显示和状态标签样式。
    def _update_elevator_state(
        self, elevator_id: int, floor: int, status: str, direction: int
    ) -> None:
        self.floor_lcds[elevator_id].display(floor)
        label = self.status_labels[elevator_id]
        label.setText(status)
        label.setProperty("status", status)
        label.style().unpolish(label)
        label.style().polish(label)

    # 接收电梯到站服务信号，恢复内部按钮和外部请求按钮的正常颜色。
    def _handle_request_served(
        self, elevator_id: int, floor: int, directions: list, had_internal: bool
    ) -> None:
        internal = self.internal_buttons.get((elevator_id, floor))
        if internal:
            internal.setProperty("active", False)
            internal.style().unpolish(internal)
            internal.style().polish(internal)

        for direction in directions:
            button = self.external_buttons.get((floor, direction))
            if button:
                button.setProperty("active", False)
                button.setEnabled(True)
                button.style().unpolish(button)
                button.style().polish(button)

    # 向运行日志区域追加一行文本，并自动滚动到底部显示最新日志。
    def _append_log(self, message: str) -> None:
        self.log_edit.append(message)
        scrollbar = self.log_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # 设置整个界面的 Qt stylesheet，包括窗口背景、按钮、状态标签、日志框和 LCD 样式。
    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                font-family: "Microsoft YaHei", "SimHei", Arial;
                font-size: 13px;
                color: #1f2933;
            }
            QMainWindow {
                background: #eef2f6;
            }
            QLabel#Title {
                font-size: 24px;
                font-weight: 700;
                padding: 8px;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #cfd8e3;
                border-radius: 6px;
                margin-top: 10px;
                font-weight: 700;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QPushButton {
                background: #f8fafc;
                border: 1px solid #b9c4d0;
                border-radius: 4px;
                padding: 5px 8px;
            }
            QPushButton:hover {
                background: #e8f1ff;
                border-color: #6ea8fe;
            }
            QPushButton:disabled {
                color: #94a3b8;
                background: #e5e7eb;
            }
            QPushButton[active="true"] {
                color: white;
                background: #ef4444;
                border-color: #b91c1c;
                font-weight: 700;
            }
            QLabel#StatusLabel {
                border-radius: 4px;
                padding: 6px;
                background: #e5e7eb;
                font-weight: 700;
            }
            QLabel#StatusLabel[status="上行"] {
                background: #dbeafe;
                color: #1d4ed8;
            }
            QLabel#StatusLabel[status="下行"] {
                background: #dcfce7;
                color: #15803d;
            }
            QLabel#StatusLabel[status="开门"] {
                background: #fef3c7;
                color: #b45309;
            }
            QLabel#StatusLabel[status="暂停"] {
                background: #fee2e2;
                color: #b91c1c;
            }
            QTextEdit {
                background: #0f172a;
                color: #e5e7eb;
                border: 1px solid #1e293b;
                border-radius: 4px;
                padding: 6px;
            }
            QLCDNumber {
                background: #111827;
                color: #22c55e;
                border: 2px solid #334155;
                border-radius: 6px;
            }
            QFrame {
                border: none;
            }
            """
        )
