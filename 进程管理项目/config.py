"""电梯调度模拟系统的基础配置。"""

FLOOR_COUNT = 20
ELEVATOR_COUNT = 5

MIN_FLOOR = 1
MAX_FLOOR = FLOOR_COUNT

# 运行速度：每移动一层的时间，单位为秒。
MOVE_INTERVAL = 0.85

# 到站开门停留时间，单位为秒。
DOOR_OPEN_TIME = 2.0

# 线程空闲轮询间隔，单位为秒。
IDLE_INTERVAL = 0.12

