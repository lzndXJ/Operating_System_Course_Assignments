"""电梯线程模型。

每部电梯使用一个 QThread 独立运行。线程只维护电梯状态并发送信号，
不直接操作任何 GUI 控件，符合 PyQt 多线程编程要求。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import List, Set, Tuple

from PyQt5.QtCore import QThread, pyqtSignal

from config import DOOR_OPEN_TIME, IDLE_INTERVAL, MAX_FLOOR, MIN_FLOOR, MOVE_INTERVAL


Direction = str  # "up" / "down"


@dataclass(frozen=True)
class ElevatorSnapshot:
    elevator_id: int
    current_floor: int
    direction: int
    status: str
    paused: bool
    target_count: int


class ElevatorThread(QThread):
    """单部电梯线程。

    targets 保存所有目标楼层；external_requests 额外记录外部请求方向，
    便于到站后通知主窗口恢复外部按钮颜色。
    """

    state_changed = pyqtSignal(int, int, str, int)
    log_message = pyqtSignal(str)
    request_served = pyqtSignal(int, int, list, bool)

    # 初始化单部电梯的线程对象，设置初始楼层、状态、目标队列和线程锁。
    def __init__(self, elevator_id: int, parent=None):
        super().__init__(parent)
        self.elevator_id = elevator_id
        self.current_floor = MIN_FLOOR
        self.direction = 0
        self.status = "静止"
        self.paused = False
        self._running = True
        self._targets: Set[int] = set()
        self._external_requests: Set[Tuple[int, Direction]] = set()
        self._lock = threading.RLock()

    # 登记电梯内部楼层请求，把乘客点击的目标楼层加入本电梯目标队列。
    def add_internal_target(self, floor: int) -> None:
        """登记电梯内部楼层按钮请求。"""
        if not MIN_FLOOR <= floor <= MAX_FLOOR:
            return
        with self._lock:
            self._targets.add(floor)
        self.log_message.emit(f"[电梯{self.elevator_id}] 内部登记 {floor}楼")

    # 登记调度器分配来的外部请求，同时记录请求方向，便于到站后恢复外部按钮颜色。
    def add_external_request(self, floor: int, direction: Direction) -> None:
        """登记由调度器分配过来的外部请求。"""
        if not MIN_FLOOR <= floor <= MAX_FLOOR:
            return
        with self._lock:
            self._targets.add(floor)
            self._external_requests.add((floor, direction))

    # 设置电梯暂停或继续运行，并通过信号通知界面刷新状态。
    def set_paused(self, paused: bool) -> None:
        with self._lock:
            self.paused = paused
            self.status = "暂停" if paused else "静止"
        action = "暂停" if paused else "启动"
        self.log_message.emit(f"[电梯{self.elevator_id}] {action}")
        self._emit_state()

    # 停止电梯线程，程序关闭窗口时调用，用于安全退出线程循环。
    def stop(self) -> None:
        with self._lock:
            self._running = False

    # 获取电梯当前状态快照，供调度器判断哪部电梯最适合响应外部请求。
    def snapshot(self) -> ElevatorSnapshot:
        with self._lock:
            return ElevatorSnapshot(
                elevator_id=self.elevator_id,
                current_floor=self.current_floor,
                direction=self.direction,
                status=self.status,
                paused=self.paused,
                target_count=len(self._targets),
            )

    # 电梯线程主循环：不断检查暂停状态和目标队列，决定移动、等待或开门。
    def run(self) -> None:
        self._emit_state()
        while True:
            with self._lock:
                if not self._running:
                    break
                paused = self.paused

            if paused:
                self._sleep_in_slices(IDLE_INTERVAL)
                continue

            target = self._choose_next_target()
            if target is None:
                with self._lock:
                    self.direction = 0
                    self.status = "静止"
                self._emit_state()
                self._sleep_in_slices(IDLE_INTERVAL)
                continue

            self._move_one_floor_towards(target)
            self._serve_current_floor_if_needed()

    # 根据当前方向和目标队列选择下一目标楼层，采用简化 SCAN 调度思想。
    def _choose_next_target(self) -> int | None:
        """选择下一目标楼层，采用简化 SCAN 思路。"""
        with self._lock:
            if not self._targets:
                return None

            floors = sorted(self._targets)
            if self.direction >= 0:
                upward = [floor for floor in floors if floor >= self.current_floor]
                if upward:
                    return upward[0]
                return floors[-1]

            downward = [floor for floor in floors if floor <= self.current_floor]
            if downward:
                return downward[-1]
            return floors[0]

    # 控制电梯向目标楼层移动一层，并发送移动日志和状态刷新信号。
    def _move_one_floor_towards(self, target: int) -> None:
        with self._lock:
            if target == self.current_floor:
                return
            old_floor = self.current_floor
            self.direction = 1 if target > self.current_floor else -1
            self.status = "上行" if self.direction > 0 else "下行"

        self._emit_state()
        self._sleep_in_slices(MOVE_INTERVAL)

        with self._lock:
            if self.paused or not self._running:
                return
            self.current_floor += self.direction
            new_floor = self.current_floor
            status = self.status

        self.log_message.emit(f"[电梯{self.elevator_id}] 从{old_floor}楼{status}到{new_floor}楼")
        self._emit_state()

    # 检查当前楼层是否需要服务；如果到达目标楼层，则开门、清除请求并通知界面恢复按钮。
    def _serve_current_floor_if_needed(self) -> None:
        with self._lock:
            if self.current_floor not in self._targets or self.paused:
                return

            floor = self.current_floor
            served_directions = [
                direction for req_floor, direction in self._external_requests if req_floor == floor
            ]
            had_internal = floor in self._targets
            self._targets.discard(floor)
            self._external_requests = {
                item for item in self._external_requests if item[0] != floor
            }
            self.direction = 0
            self.status = "开门"

        self.log_message.emit(f"[电梯{self.elevator_id}] 到达{floor}楼，开门")
        self.request_served.emit(self.elevator_id, floor, served_directions, had_internal)
        self._emit_state()
        self._sleep_in_slices(DOOR_OPEN_TIME)

        with self._lock:
            if not self.paused:
                self.status = "静止"
        self._emit_state()

    # 分片睡眠，让电梯在等待移动或开门时仍能较快响应暂停和关闭操作。
    def _sleep_in_slices(self, seconds: float) -> None:
        """分片睡眠，便于暂停和退出能较快生效。"""
        end_time = time.time() + seconds
        while time.time() < end_time:
            with self._lock:
                if not self._running:
                    return
            time.sleep(min(0.05, end_time - time.time()))

    # 发送电梯当前状态信号，由主线程接收后更新 LCD 和状态标签。
    def _emit_state(self) -> None:
        with self._lock:
            self.state_changed.emit(
                self.elevator_id, self.current_floor, self.status, self.direction
            )
