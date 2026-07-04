"""电梯调度器。

调度规则：
1. 优先选择空闲且距离最近的电梯；
2. 没有空闲电梯时，选择运行方向一致且顺路的电梯；
3. 都不满足时，选择任务数量较少且距离较近的电梯。
"""

from __future__ import annotations

from typing import List

from PyQt5.QtCore import QObject, pyqtSignal

from elevator import Direction, ElevatorSnapshot, ElevatorThread


class ElevatorScheduler(QObject):
    log_message = pyqtSignal(str)

    # 初始化调度器，保存所有电梯线程对象，后续用于分配外部请求。
    def __init__(self, elevators: List[ElevatorThread], parent=None):
        super().__init__(parent)
        self.elevators = elevators

    # 处理楼层外部请求：根据当前电梯状态选择合适电梯，并把请求加入该电梯队列。
    def dispatch_external_request(self, floor: int, direction: Direction) -> int:
        snapshots = [elevator.snapshot() for elevator in self.elevators]
        chosen = self._choose_elevator(snapshots, floor, direction)
        elevator = self.elevators[chosen.elevator_id - 1]
        elevator.add_external_request(floor, direction)

        direction_text = "上行" if direction == "up" else "下行"
        self.log_message.emit(
            f"[调度器] {floor}楼{direction_text}请求分配给电梯{chosen.elevator_id}"
        )
        return chosen.elevator_id

    # 调度核心算法：按“空闲最近、同向顺路、任务少且距离近”的顺序选择电梯。
    def _choose_elevator(
        self, snapshots: List[ElevatorSnapshot], floor: int, direction: Direction
    ) -> ElevatorSnapshot:
        available = [item for item in snapshots if not item.paused]
        if not available:
            available = snapshots

        idle = [item for item in available if item.direction == 0 and item.status in ("静止", "开门")]
        if idle:
            return min(idle, key=lambda item: abs(item.current_floor - floor))

        same_way = [
            item
            for item in available
            if self._is_on_the_way(item, floor, direction)
        ]
        if same_way:
            return min(same_way, key=lambda item: abs(item.current_floor - floor))

        return min(
            available,
            key=lambda item: (item.target_count, abs(item.current_floor - floor)),
        )

    @staticmethod
    # 判断某部正在运行的电梯是否与外部请求方向一致，并且经过请求楼层。
    def _is_on_the_way(snapshot: ElevatorSnapshot, floor: int, direction: Direction) -> bool:
        if direction == "up":
            return snapshot.direction > 0 and snapshot.current_floor <= floor
        return snapshot.direction < 0 and snapshot.current_floor >= floor
