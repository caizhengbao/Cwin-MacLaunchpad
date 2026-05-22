# -*- coding: utf-8 -*-
"""
搜索栏组件
macOS Launchpad 风格的搜索栏，支持拼音搜索。
"""

from PyQt5.QtWidgets import QWidget, QLineEdit, QHBoxLayout
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QRectF

class SearchIconWidget(QWidget):
    """自定义绘制的搜索图标"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        pen = QPen(QColor(255, 255, 255, 128))
        pen.setWidth(2)
        painter.setPen(pen)
        
        # 绘制放大镜圆圈
        painter.drawEllipse(3, 3, 10, 10)
        # 绘制放大镜把手
        pen.setWidth(2)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(11, 11, 16, 16)
        painter.end()


class SearchBar(QWidget):
    """macOS 风格搜索栏"""

    text_changed = pyqtSignal(str)

    def __init__(self, width: int = 260, height: int = 36, parent=None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 防抖计时器
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(150)
        self._debounce_timer.timeout.connect(self._emit_text)

        # 布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        # 搜索图标标签（使用 QPainter 绘制）
        self._icon_label = SearchIconWidget()
        layout.addWidget(self._icon_label)

        # 输入框
        self._input = QLineEdit()
        self._input.setPlaceholderText("搜索")
        self._input.textChanged.connect(self._on_text_changed)

        self._input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: rgba(255, 255, 255, 0.9);
                font-size: 15px;
                font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
                padding: 0;
                selection-background-color: rgba(255, 255, 255, 0.25);
            }
            QLineEdit::placeholder {
                color: rgba(255, 255, 255, 0.45);
            }
        """)
        layout.addWidget(self._input)

    def paintEvent(self, event):
        """绘制圆角毛玻璃背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # 背景 (胶囊形状 Capsule)
        radius = self.height() / 2
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), radius, radius)
        painter.fillPath(path, QColor(255, 255, 255, 30))

        # 边框 (取消实体边框，使用极度轻微的内阴影效果)
        painter.setPen(QPen(QColor(255, 255, 255, 10), 1))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
                                 radius, radius)
        painter.end()

    def _on_text_changed(self, text: str):
        """输入文字变化（防抖）"""
        self._debounce_timer.start()

    def _emit_text(self):
        """防抖后发射信号"""
        self.text_changed.emit(self._input.text().strip())

    def clear(self):
        """清空搜索框"""
        self._input.clear()

    def text(self) -> str:
        return self._input.text().strip()

    def focus_input(self):
        """聚焦到输入框"""
        self._input.setFocus()

    def has_focus(self) -> bool:
        return self._input.hasFocus()
