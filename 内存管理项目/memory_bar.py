"""Custom widget used to draw a proportional memory layout bar."""

from typing import Optional

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QTextOption
from PyQt5.QtWidgets import QSizePolicy, QWidget

from memory_manager import MemoryManager


class MemoryBar(QWidget):
    def __init__(self, parent=None) -> None:
        # 初始化内存分布图控件。
        super().__init__(parent)
        self.manager: Optional[MemoryManager] = None
        self.setMinimumHeight(130)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_manager(self, manager: MemoryManager) -> None:
        # 设置要绘制的内存管理器。
        self.manager = manager
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt method name
        # 绘制横向比例内存条。
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))

        margin_x = 14
        bar_top = 28
        bar_height = 74
        bar_rect = QRectF(margin_x, bar_top, max(1, self.width() - margin_x * 2), bar_height)

        painter.setPen(QPen(QColor("#94a3b8"), 1))
        painter.setBrush(QColor("#f8fafc"))
        painter.drawRoundedRect(bar_rect, 4, 4)

        if self.manager is None or self.manager.total_size <= 0:
            self._draw_centered(painter, bar_rect, "未初始化")
            painter.end()
            return

        total_size = self.manager.total_size
        segments = self.manager.get_memory_segments()
        for segment in segments:
            start = int(segment["start"])
            size = int(segment["size"])
            if size <= 0:
                continue

            x = bar_rect.left() + bar_rect.width() * start / total_size
            width = bar_rect.width() * size / total_size
            if start + size >= total_size:
                width = bar_rect.right() - x
            segment_rect = QRectF(x, bar_rect.top(), max(1.0, width), bar_rect.height())

            color = self._segment_color(str(segment["name"]), str(segment["kind"]))
            painter.setPen(QPen(QColor("#475569"), 1))
            painter.setBrush(color)
            painter.drawRect(segment_rect)

            label = self._segment_label(segment, segment_rect.width())
            if label:
                painter.save()
                painter.setClipRect(segment_rect.adjusted(1, 1, -1, -1))
                painter.setPen(QColor("#111827"))
                font = QFont()
                font.setPointSize(9)
                painter.setFont(font)
                option = QTextOption()
                option.setAlignment(Qt.AlignCenter)
                option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
                painter.drawText(segment_rect.adjusted(3, 3, -3, -3), label, option)
                painter.restore()

        painter.setPen(QColor("#475569"))
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(QRectF(bar_rect.left(), 106, 110, 18), Qt.AlignLeft | Qt.AlignVCenter, "0K")
        painter.drawText(
            QRectF(bar_rect.right() - 130, 106, 130, 18),
            Qt.AlignRight | Qt.AlignVCenter,
            f"{total_size - 1}K",
        )
        painter.end()

    def _draw_centered(self, painter: QPainter, rect: QRectF, text: str) -> None:
        # 在指定区域居中绘制提示文字。
        painter.setPen(QColor("#64748b"))
        painter.drawText(rect, Qt.AlignCenter, text)

    def _segment_label(self, segment, width: float) -> str:
        # 根据分区宽度生成合适的显示文字。
        name = str(segment["name"])
        start = int(segment["start"])
        end = int(segment["end"])
        size = int(segment["size"])
        if width < 22:
            return ""
        if width < 52:
            return name
        if width < 92:
            return f"{name}\n{size}K"
        return f"{name}\n{start}-{end}K\n{size}K"

    def _segment_color(self, name: str, kind: str) -> QColor:
        # 根据分区类型和作业名选择颜色。
        if kind == "free":
            return QColor("#e5e7eb")

        palette = [
            "#7dd3fc",
            "#86efac",
            "#fca5a5",
            "#fde68a",
            "#c4b5fd",
            "#fdba74",
            "#67e8f9",
            "#f9a8d4",
            "#bef264",
            "#93c5fd",
        ]
        digits = "".join(ch for ch in name if ch.isdigit())
        if digits:
            index = (int(digits) - 1) % len(palette)
        else:
            index = sum(ord(ch) for ch in name) % len(palette)
        return QColor(palette[index])
