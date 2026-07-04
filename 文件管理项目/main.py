import sys

from qt_compat import QApplication, QT_LIB, run_app
from ui_main import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("FileSystemManager")
    window = MainWindow()
    window.statusBar().showMessage(f"当前 Qt 绑定：{QT_LIB}")
    window.show()
    return run_app(app)


if __name__ == "__main__":
    raise SystemExit(main())
