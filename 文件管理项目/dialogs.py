from qt_compat import QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, Qt


class TextInputDialog(QDialog):
    def __init__(self, title: str, label: str, multiline: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.resize(420, 260 if multiline else 120)
        self.multiline = multiline
        layout = QVBoxLayout(self)
        form = QFormLayout()
        if multiline:
            self.editor = QTextEdit()
            form.addRow(QLabel(label), self.editor)
        else:
            self.editor = QLineEdit()
            form.addRow(label, self.editor)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def value(self) -> str:
        if self.multiline:
            return self.editor.toPlainText()
        return self.editor.text().strip()


class InfoDialog(QDialog):
    def __init__(self, title: str, text: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.resize(860, 560)
        layout = QVBoxLayout(self)
        viewer = QTextEdit()
        viewer.setReadOnly(True)
        viewer.setLineWrapMode(QTextEdit.NoWrap)
        viewer.setPlainText(text)
        layout.addWidget(viewer)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
