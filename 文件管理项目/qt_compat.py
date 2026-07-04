try:
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QColor, QBrush
    from PyQt5.QtWidgets import (
        QAction,
        QApplication,
        QDialog,
        QFormLayout,
        QGridLayout,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPushButton,
        QPlainTextEdit,
        QSplitter,
        QSizePolicy,
        QStyleFactory,
        QTableWidget,
        QTableWidgetItem,
        QAbstractItemView,
        QTextEdit,
        QToolBar,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    QT_LIB = "PyQt5"
except ImportError:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QAction, QColor, QBrush
    from PySide6.QtWidgets import (
        QApplication,
        QDialog,
        QFormLayout,
        QGridLayout,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPushButton,
        QPlainTextEdit,
        QSplitter,
        QSizePolicy,
        QStyleFactory,
        QTableWidget,
        QTableWidgetItem,
        QAbstractItemView,
        QTextEdit,
        QToolBar,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    QT_LIB = "PySide6"


def run_dialog(dialog):
    exec_fn = getattr(dialog, "exec_", None) or getattr(dialog, "exec")
    return exec_fn()


def run_app(app):
    exec_fn = getattr(app, "exec_", None) or getattr(app, "exec")
    return exec_fn()


def run_menu(menu, pos):
    exec_fn = getattr(menu, "exec_", None) or getattr(menu, "exec")
    return exec_fn(pos)
