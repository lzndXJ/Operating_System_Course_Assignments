# 基于 Python 多线程与 PyQt5 的五电梯调度模拟系统

## 1. 题目要求

本项目要求使用 **Python + PyQt5** 实现一个五电梯调度模拟系统，用于模拟操作系统课程中多线程、同步和调度算法的思想。

系统模拟一栋 **20 层楼** 和 **5 部电梯**，所有电梯初始状态都在 1 楼。每部电梯需要具有当前楼层显示、内部楼层按钮、运行状态显示、暂停/启动按钮。楼层外部需要提供上行和下行请求按钮，请求登记后按钮变色，电梯响应后恢复正常。

项目还要求体现多线程思想：每部电梯使用独立线程模拟运行，界面更新通过信号通知主线程完成，子线程不能直接操作 GUI 控件，共享状态需要使用锁保护。

## 2. 开发环境的配置

开发环境：

- 操作系统：Windows 11
- 编程语言：Python 3.10
- GUI 框架：PyQt5
- 开发工具：Visual Studio Code

安装依赖：

```bash
pip install PyQt5
```

如果使用 Anaconda 管理 Python 环境，需要先进入本项目对应的 conda 环境。例如：

```bash
conda activate 你的环境名
```

然后在该环境中安装 PyQt5 和 PyInstaller：

```bash
pip install PyQt5
pip install pyinstaller
```

注意：PyInstaller 必须安装在能够正常运行本项目的 Python/conda 环境中。也就是说，在哪个环境里可以运行 `python main.py`，就应该在哪个环境里安装 PyInstaller 并进行打包。

运行方式：

```bash
python main.py
```

生成 Windows 可执行程序：

```bash
pyinstaller --onefile --windowed --name ElevatorDispatching main.py
```

或者使用当前环境的 Python 显式调用 PyInstaller：

```bash
python -m PyInstaller --onefile --windowed --name ElevatorDispatching main.py
```

参数说明：

- `--onefile`：将程序打包成单个 exe 文件。
- `--windowed`：运行 GUI 程序时不显示黑色命令行窗口。
- `--name ElevatorSystem`：指定生成的可执行程序名称。
- `main.py`：项目入口文件。

打包完成后，可执行文件位于：

```text
dist/ElevatorSystem.exe
```

项目结构：

```text
.
├── main.py        程序入口
├── config.py      楼层数、电梯数、运行速度等配置
├── elevator.py    电梯线程与电梯运行逻辑
├── scheduler.py   外部请求调度算法
├── window.py      PyQt5 图形界面
└── README.md      项目说明文档
```

## 3. 具体算法

### 3.1 外部请求分配算法

当用户点击楼层外部的上行或下行按钮时，请求会交给调度器处理。调度器先获取每部电梯的当前状态快照，再根据调度规则选择一部合适的电梯。

核心代码位于 `scheduler.py`：

```python
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
```

调度规则分为三步：

1. 优先选择空闲且距离最近的电梯。
2. 没有空闲电梯时，选择运行方向一致且顺路的电梯。
3. 如果仍不满足，则选择任务数量较少且距离较近的电梯。

对应代码如下：

```python
def _choose_elevator(
    self, snapshots: List[ElevatorSnapshot], floor: int, direction: Direction
) -> ElevatorSnapshot:
    available = [item for item in snapshots if not item.paused]
    if not available:
        available = snapshots

    idle = [
        item for item in available
        if item.direction == 0 and item.status in ("静止", "开门")
    ]
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
```

判断“同向顺路”的代码如下：

```python
@staticmethod
def _is_on_the_way(snapshot: ElevatorSnapshot, floor: int, direction: Direction) -> bool:
    if direction == "up":
        return snapshot.direction > 0 and snapshot.current_floor <= floor
    return snapshot.direction < 0 and snapshot.current_floor >= floor
```

### 3.2 电梯内部请求算法

每部电梯内部有 1-20 层按钮。点击按钮后，该楼层直接加入当前电梯自己的目标队列。目标队列使用集合保存，避免重复登记同一楼层。

核心代码位于 `elevator.py`：

```python
def add_internal_target(self, floor: int) -> None:
    if not MIN_FLOOR <= floor <= MAX_FLOOR:
        return
    with self._lock:
        self._targets.add(floor)
    self.log_message.emit(f"[电梯{self.elevator_id}] 内部登记 {floor}楼")
```

外部请求被调度器分配给某部电梯后，也会加入该电梯目标队列，同时记录请求方向，方便电梯到站后恢复右侧外部按钮颜色。

```python
def add_external_request(self, floor: int, direction: Direction) -> None:
    if not MIN_FLOOR <= floor <= MAX_FLOOR:
        return
    with self._lock:
        self._targets.add(floor)
        self._external_requests.add((floor, direction))
```

### 3.3 电梯线程运行算法

每部电梯继承 `QThread`，在自己的线程中循环运行。线程不断检查是否暂停、是否有目标楼层，然后执行移动和到站服务。

核心代码如下：

```python
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
```

这个循环体现了操作系统中线程反复检查任务、执行任务、等待任务的过程。

### 3.4 下一目标楼层选择算法

电梯选择目标时采用简化的 SCAN 思想：如果当前方向是向上，则优先选择当前楼层以上最近的目标；如果当前方向是向下，则优先选择当前楼层以下最近的目标。当前方向没有目标时，再反向寻找目标。

```python
def _choose_next_target(self) -> int | None:
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
```

### 3.5 电梯移动算法

电梯每次只移动一层。移动前先根据目标楼层判断方向，然后等待设定的运行时间，最后更新当前楼层并发送状态信号。

```python
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

    self.log_message.emit(
        f"[电梯{self.elevator_id}] 从{old_floor}楼{status}到{new_floor}楼"
    )
    self._emit_state()
```

### 3.6 到站开门与请求清除算法

当电梯到达目标楼层后，需要清除该楼层的内部请求和外部请求，并发送信号通知主窗口恢复按钮颜色。

```python
def _serve_current_floor_if_needed(self) -> None:
    with self._lock:
        if self.current_floor not in self._targets or self.paused:
            return

        floor = self.current_floor
        served_directions = [
            direction
            for req_floor, direction in self._external_requests
            if req_floor == floor
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
```

### 3.7 线程安全与 GUI 更新算法

为了避免多个线程同时修改共享状态，电梯类中使用 `threading.RLock()` 保护关键数据，例如当前楼层、运行方向、目标队列和暂停状态。

```python
self._targets: Set[int] = set()
self._external_requests: Set[Tuple[int, Direction]] = set()
self._lock = threading.RLock()
```

子线程不直接操作 GUI，而是通过 `pyqtSignal` 发送信号：

```python
state_changed = pyqtSignal(int, int, str, int)
log_message = pyqtSignal(str)
request_served = pyqtSignal(int, int, list, bool)
```

主窗口中连接信号和槽函数：

```python
def _connect_signals(self) -> None:
    self.scheduler.log_message.connect(self._append_log)
    for elevator in self.elevators:
        elevator.state_changed.connect(self._update_elevator_state)
        elevator.log_message.connect(self._append_log)
        elevator.request_served.connect(self._handle_request_served)
```

主线程收到信号后更新 LCD、状态标签和按钮颜色：

```python
def _update_elevator_state(
    self, elevator_id: int, floor: int, status: str, direction: int
) -> None:
    self.floor_lcds[elevator_id].display(floor)
    label = self.status_labels[elevator_id]
    label.setText(status)
    label.setProperty("status", status)
    label.style().unpolish(label)
    label.style().polish(label)
```

## 4. 功能

本系统实现了以下功能：

- 五部电梯并发运行模拟。
- 20 层楼层调度。
- 每部电梯显示当前楼层 LCD。
- 每部电梯显示状态：静止、上行、下行、开门、暂停。
- 每部电梯提供 1-20 层内部按钮。
- 每部电梯提供暂停/启动按钮。
- 右侧提供每层楼的外部上行、下行请求按钮。
- 外部请求按钮点击后变红，表示请求已登记。
- 电梯响应请求后，对应按钮恢复正常颜色。
- 调度器自动分配外部请求。
- 运行日志实时显示调度分配、电梯移动和到站开门过程。
- 程序启动后自动最大化显示，便于演示。

## 5. 心得体会

通过本次课程设计，我对操作系统中的多线程、同步和调度思想有了更直观的理解。五部电梯分别由独立线程模拟运行，每个线程都有自己的运行状态和任务队列，这与操作系统中多个进程或线程并发执行的思想相似。

在实现过程中，我认识到 GUI 程序中的多线程不能随意直接操作界面控件。PyQt5 要求界面更新在主线程中完成，因此本项目使用 `pyqtSignal` 让电梯线程把楼层、状态和日志发送给主线程，再由主线程统一更新界面。这样既能保持界面响应，也能避免线程安全问题。

调度算法方面，本项目采用了“空闲最近优先、同向顺路优先、任务少且距离近优先”的规则。虽然该算法不是最复杂的最优算法，但逻辑清晰、易于实现，能够较好地模拟现实电梯调度的基本过程。

本项目也让我体会到课程设计不仅要让程序能运行，还要考虑界面是否清晰、操作是否方便、日志是否有助于观察系统行为。通过日志区域，可以清楚看到请求如何被分配、电梯如何移动、何时到达并开门，这对理解调度过程非常有帮助。

总体来说，本项目把操作系统课程中的线程、同步、共享状态保护和调度策略与图形化程序结合起来，加深了我对课程内容的理解，也提高了我使用 Python 和 PyQt5 开发完整应用程序的能力。
