"""程序入口。

运行命令：
    python main.py
"""

import sys

from PyQt5.QtWidgets import QApplication

from window import MainWindow


# 程序主入口：创建 PyQt 应用对象、创建主窗口并启动事件循环。
def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    # 启动后直接最大化，避免初始窗口过窄导致界面内容显示到屏幕外。
    window.showMaximized()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
