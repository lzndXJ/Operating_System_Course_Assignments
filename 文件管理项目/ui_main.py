from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Union

from dialogs import InfoDialog, TextInputDialog
from filesystem import END_BLOCK, FileSystemError
from models import Directory, FileEntry
from qt_compat import (
    QAction,
    QAbstractItemView,
    QBrush,
    QColor,
    QGridLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QSplitter,
    QStyleFactory,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    Qt,
    run_dialog,
    run_menu,
)
import storage


USER_ROLE = 256


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.fs = storage.load_or_create()
        self.forward_stack: List[Directory] = []
        self.changed = False
        self.setWindowTitle("File Management | 文件管理 - Virtual File System Manager (VFSM)")
        self.resize(940, 668)
        self.setMinimumSize(820, 560)
        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        self._build_menu()
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(4)

        nav = QWidget()
        nav_layout = QGridLayout(nav)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(4)
        self.back_btn = QPushButton("<")
        self.forward_btn = QPushButton(">")
        self.back_btn.setFixedSize(28, 28)
        self.forward_btn.setFixedSize(28, 28)
        self.back_btn.clicked.connect(self.action_back)
        self.forward_btn.clicked.connect(self.action_forward)
        self.path_text = QLineEdit()
        self.path_text.setReadOnly(True)
        self.path_text.setMinimumHeight(28)
        self.path_text.setMaximumHeight(28)
        nav_layout.addWidget(self.back_btn, 0, 0)
        nav_layout.addWidget(self.forward_btn, 0, 1)
        nav_layout.addWidget(self.path_text, 0, 2)
        nav.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(nav, 0)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setItemsExpandable(True)
        self.tree.setIndentation(24)
        self.tree.setUniformRowHeights(True)
        windows_style = QStyleFactory.create("Windows")
        if windows_style is not None:
            self.tree.setStyle(windows_style)
        self.tree.itemDoubleClicked.connect(self.on_tree_double_clicked)
        self.tree.itemClicked.connect(self.on_tree_clicked)
        splitter.addWidget(self.tree)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["文件名 / 文件夹名", "修改时间", "文件类型", "物理地址", "文件大小"])
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        for column in range(5):
            header.setSectionResizeMode(column, QHeaderView.Interactive)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.cellDoubleClicked.connect(self.on_table_double_clicked)
        splitter.addWidget(self.table)
        splitter.setSizes([255, 655])
        layout.addWidget(splitter, 1)

        self.status_label = QLabel()
        self.status_label.setMaximumHeight(24)
        layout.addWidget(self.status_label, 0)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(70)
        self.log_box.setMaximumHeight(90)
        self.log_box.setPlaceholderText("操作日志")
        layout.addWidget(self.log_box, 0)
        self.setCentralWidget(root)

        self._apply_style()

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("文件(&F)")
        self._add_action(file_menu, "从本地加载", self.action_load, "Ctrl+L")
        self._add_action(file_menu, "保存至本地", self.action_save, "Ctrl+S")
        file_menu.addSeparator()
        self._add_action(file_menu, "格式化", self.action_format, "Ctrl+R")

        op_menu = self.menuBar().addMenu("操作(&O)")
        create_menu = op_menu.addMenu("新建")
        self._add_action(create_menu, "文本文件", self.action_create_text, "Ctrl+T")
        self._add_action(create_menu, "文件夹", self.action_create_folder, "Ctrl+F")
        self._add_action(op_menu, "打开", self.action_open, "Ctrl+O")
        self._add_action(op_menu, "删除", self.action_delete, "Ctrl+D")
        self._add_action(op_menu, "重命名", self.action_rename, "Ctrl+N")

        view_menu = self.menuBar().addMenu("查看(&V)")
        self._add_action(view_menu, "FAT 表与位图", self.action_fat_bitmap, "Ctrl+B")
        self._add_action(view_menu, "文件属性", self.action_properties, "Ctrl+I")

    def _add_action(self, menu: QMenu, text: str, handler, shortcut: Optional[str] = None) -> QAction:
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(handler)
        menu.addAction(action)
        return action

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #ffffff; font-family: "Microsoft YaHei UI", "Microsoft YaHei"; font-size: 10pt; }
            QMenuBar { background: #ffffff; }
            QMenuBar::item:selected, QMenu::item:selected { background: #e7f1ff; }
            QLineEdit { border: 1px solid #aeb7c2; padding-left: 8px; background: #ffffff; font-size: 12pt; }
            QPushButton { background: #ffffff; border: 1px solid #b9c2cc; font-weight: 700; }
            QPushButton:hover { background: #eef6ff; }
            QTreeWidget, QTableWidget { border: 1px solid #8f98a3; background: #ffffff; gridline-color: #eeeeee; }
            QTreeWidget::item { min-height: 24px; }
            QHeaderView::section { background: #ffffff; border: 0; border-right: 1px solid #e6e6e6; padding: 5px; font-weight: 500; }
            QPlainTextEdit { border: 1px solid #d4dbe3; background: #fbfcfe; color: #36404a; }
            """
        )

    def refresh_all(self) -> None:
        self.refresh_tree()
        self.refresh_table()
        self.refresh_path()
        self.refresh_status()

    def refresh_tree(self) -> None:
        self.tree.clear()
        root_item = QTreeWidgetItem(["📁 根目录"])
        root_item.setData(0, USER_ROLE, "/")
        self.tree.addTopLevelItem(root_item)
        self._fill_tree(self.fs.root, root_item)
        self.tree.expandAll()

    def _fill_tree(self, directory: Directory, parent_item: QTreeWidgetItem) -> None:
        for entry in self.fs.list_dir(directory):
            icon = "📁" if isinstance(entry, Directory) else "📄"
            item = QTreeWidgetItem([f"{icon} {entry.name}"])
            item.setData(0, USER_ROLE, self._entry_path(directory, entry.name))
            parent_item.addChild(item)
            if isinstance(entry, Directory):
                self._fill_tree(entry, item)

    def refresh_table(self) -> None:
        entries = self.fs.list_dir()
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            if isinstance(entry, Directory):
                values = [f"📁 {entry.name}", entry.modified_time, "文件夹", "-", f"{len(entry.children)} 项"]
                color = QColor("#fffdf2")
            else:
                start_block = "-" if entry.start_block == END_BLOCK else str(entry.start_block)
                values = [f"📄 {entry.name}", entry.modified_time, "文本文件", start_block, f"{entry.size} B"]
                color = QColor("#f7f7f7") if entry.is_open else QColor("#ffffff")
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(USER_ROLE, entry.name)
                item.setBackground(QBrush(color))
                self.table.setItem(row, col, item)
        self.resize_table_columns()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.resize_table_columns()

    def resize_table_columns(self) -> None:
        if not hasattr(self, "table"):
            return
        width = max(self.table.viewport().width() - 8, 600)
        ratios = [0.42, 0.24, 0.13, 0.10, 0.11]
        for column, ratio in enumerate(ratios):
            self.table.setColumnWidth(column, int(width * ratio))

    def refresh_path(self) -> None:
        self.path_text.setText("> " + self.display_path(self.fs.current_dir))
        self.back_btn.setEnabled(self.fs.current_dir.parent is not None)
        self.forward_btn.setEnabled(bool(self.forward_stack))

    def refresh_status(self) -> None:
        self.status_label.setText(
            f"虚拟磁盘：{self.fs.used_blocks}/{self.fs.block_count} 块已用，"
            f"空闲 {self.fs.free_blocks} 块，块大小 {self.fs.block_size} B，容量 {self.fs.capacity} B"
        )

    def display_path(self, directory: Directory) -> str:
        if directory.parent is None:
            return "根目录\\"
        return "根目录\\" + directory.path().strip("/").replace("/", "\\")

    def on_tree_clicked(self, item: QTreeWidgetItem) -> None:
        path = item.data(0, USER_ROLE)
        try:
            entry = self.fs.resolve_path(path)
            if isinstance(entry, FileEntry):
                self.select_name_in_table(entry.name)
        except FileSystemError:
            pass

    def on_tree_double_clicked(self, item: QTreeWidgetItem) -> None:
        path = item.data(0, USER_ROLE)
        try:
            entry = self.fs.resolve_path(path)
            if isinstance(entry, Directory):
                self.change_directory(entry, clear_forward=True)
        except FileSystemError as exc:
            self.show_error(str(exc))

    def on_table_double_clicked(self, row: int, column: int) -> None:
        self.action_open()

    def show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        create = menu.addMenu("新建")
        self._add_action(create, "文本文件", self.action_create_text)
        self._add_action(create, "文件夹", self.action_create_folder)
        menu.addSeparator()
        self._add_action(menu, "打开", self.action_open)
        self._add_action(menu, "删除", self.action_delete)
        self._add_action(menu, "重命名", self.action_rename)
        menu.addSeparator()
        self._add_action(menu, "属性", self.action_properties)
        run_menu(menu, self.table.viewport().mapToGlobal(pos))

    def action_back(self) -> None:
        if self.fs.current_dir.parent is None:
            return
        self.forward_stack.append(self.fs.current_dir)
        self.fs.current_dir = self.fs.current_dir.parent
        self.refresh_all()

    def action_forward(self) -> None:
        if not self.forward_stack:
            return
        self.fs.current_dir = self.forward_stack.pop()
        self.refresh_all()

    def action_load(self) -> None:
        try:
            self.fs = storage.load_or_create()
            self.forward_stack.clear()
            self.changed = False
            self.refresh_all()
            self.log("从本地加载虚拟磁盘文件成功")
        except Exception as exc:
            self.show_error(f"从本地加载虚拟磁盘文件失败：{exc}")

    def action_save(self) -> None:
        try:
            storage.save(self.fs)
            self.changed = False
            self.log(f"保存虚拟磁盘文件至本地：{storage.DEFAULT_STORAGE}")
            QMessageBox.information(self, "提示", "保存虚拟磁盘文件至本地成功")
        except Exception as exc:
            self.show_error(f"保存失败：{exc}")

    def action_format(self) -> None:
        if QMessageBox.question(self, "提示", "确定要格式化虚拟文件系统吗？") != QMessageBox.Yes:
            return
        self.fs.format()
        self.forward_stack.clear()
        self.mark_changed("格式化完成")

    def action_create_text(self) -> None:
        name = self.unique_name("新建文本文件", ".txt")
        self.run_fs_action(lambda: self.fs.create_file(name), f"新建文本文件：{name}")

    def action_create_folder(self) -> None:
        name = self.unique_name("新建文件夹")
        self.run_fs_action(lambda: self.fs.create_dir(name), f"新建文件夹：{name}")

    def action_open(self) -> None:
        entry = self.selected_entry()
        if entry is None:
            self.show_error("打开操作失败：请选中一个文件或文件夹")
            return
        if isinstance(entry, Directory):
            self.change_directory(entry, clear_forward=True)
            return
        try:
            self.fs.open_file(entry.name)
            content = self.fs.read_file(entry.name)
            dialog = TextInputDialog(f"编辑文本文件：{entry.name}", "文件内容：", multiline=True, parent=self)
            dialog.editor.setPlainText(content)
            if run_dialog(dialog) == dialog.Accepted:
                blocks = self.fs.write_file(entry.name, dialog.value())
                self.mark_changed(f"写入文本文件：{entry.name}，占用块：{self.blocks_text(blocks)}")
            else:
                self.refresh_all()
        except FileSystemError as exc:
            self.show_error(str(exc))
        finally:
            try:
                self.fs.close_file(entry.name)
            except FileSystemError:
                pass
            self.refresh_all()

    def action_delete(self) -> None:
        entry = self.selected_entry()
        if entry is None:
            self.show_error("删除操作失败：请选中一个文件或文件夹")
            return
        if QMessageBox.question(self, "提示", f"确定删除 {entry.name} 吗？") != QMessageBox.Yes:
            return
        self.run_fs_action(lambda: self.fs.delete_entry(entry.name), f"删除：{entry.name}")

    def action_rename(self) -> None:
        entry = self.selected_entry()
        if entry is None:
            self.show_error("重命名操作失败：请选中一个文件或文件夹")
            return
        dialog = TextInputDialog("重命名", "新名称：", parent=self)
        dialog.editor.setText(entry.name)
        if run_dialog(dialog) != dialog.Accepted:
            return
        new_name = dialog.value()
        self.run_fs_action(lambda: self.fs.rename_entry(entry.name, new_name), f"重命名：{entry.name} -> {new_name}")

    def action_fat_bitmap(self) -> None:
        owners = self.fs.block_owner_map()
        lines = ["块号    位图    FAT    所属文件"]
        for index in range(self.fs.block_count):
            lines.append(f"{index:03d}    {1 if self.fs.bitmap[index] else 0}       {self.fs.fat[index]:>3}    {owners.get(index, '-')}")
        run_dialog(InfoDialog("FAT 表与位图", "\n".join(lines), self))

    def action_properties(self) -> None:
        entry = self.selected_entry()
        if entry is None:
            self.show_error("请先选择一个文件或文件夹")
            return
        info = self.fs.entry_info(entry)
        run_dialog(InfoDialog("属性", "\n".join(f"{key}：{value}" for key, value in info.items()), self))

    def change_directory(self, directory: Directory, clear_forward: bool) -> None:
        self.fs.current_dir = directory
        if clear_forward:
            self.forward_stack.clear()
        self.refresh_all()
        self.log(f"打开文件夹：{self.display_path(directory)}")

    def run_fs_action(self, fn, success_message: str) -> None:
        try:
            fn()
            self.mark_changed(success_message)
        except FileSystemError as exc:
            self.show_error(str(exc))

    def mark_changed(self, message: str) -> None:
        self.changed = True
        self.refresh_all()
        self.log(message)

    def selected_entry(self) -> Optional[Union[Directory, FileEntry]]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        return self.fs.current_dir.get_child(item.data(USER_ROLE))

    def select_name_in_table(self, name: str) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(USER_ROLE) == name:
                self.table.selectRow(row)
                return

    def unique_name(self, base: str, ext: str = "") -> str:
        existing = set(self.fs.current_dir.children.keys())
        candidate = f"{base}{ext}"
        if candidate not in existing:
            return candidate
        index = 1
        while True:
            candidate = f"{base}({index}){ext}"
            if candidate not in existing:
                return candidate
            index += 1

    def _entry_path(self, directory: Directory, name: str) -> str:
        if directory.parent is None:
            return "/" + name
        return directory.path().rstrip("/") + "/" + name

    def blocks_text(self, blocks: List[int]) -> str:
        return " -> ".join(map(str, blocks)) if blocks else "-"

    def log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.appendPlainText(f"[{stamp}] {message}")

    def show_error(self, message: str) -> None:
        QMessageBox.warning(self, "提示", message)
        self.log(f"操作失败：{message}")

    def closeEvent(self, event) -> None:
        if self.changed:
            reply = QMessageBox.question(self, "提示", "是否保存虚拟磁盘文件至本地？")
            if reply == QMessageBox.Yes:
                storage.save(self.fs)
        event.accept()
