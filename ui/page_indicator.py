# -*- coding: utf-8 -*-
"""
页面指示点组件
底部的圆点分页指示器。
"""

from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtCore import Qt, pyqtSignal


class PageIndicator(QWidget):
    """页面指示点组件"""

    page_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._total_pages = 1
        self._current_page = 0
        self._dot_size = 8
        self._dot_spacing = 12

        self.setAttribute(Qt.WA_TranslucentBackground)
        self._update_size()

    def set_pages(self, total: int, current: int):
        """设置总页数和当前页"""
        if total < 1:
            total = 1
        self._total_pages = total
        self._current_page = max(0, min(current, total - 1))
        self._update_size()
        self.update()

    def _update_size(self):
        """根据页数更新控件宽度"""
        width = (self._dot_size * self._total_pages) + (self._dot_spacing * max(0, self._total_pages - 1))
        self.setFixedSize(width, self._dot_size)

    def paintEvent(self, event):
        """绘制圆点"""
        if self._total_pages <= 1:
            return  # 只有一页时不显示指示点

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # 颜色
        active_color = QColor(255, 255, 255, 255)
        inactive_color = QColor(255, 255, 255, 90)

        for i in range(self._total_pages):
            x = i * (self._dot_size + self._dot_spacing)
            color = active_color if i == self._current_page else inactive_color
            
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(x, 0, self._dot_size, self._dot_size)

        painter.end()

    def mousePressEvent(self, event):
        """点击指示点切换页面"""
        if event.button() == Qt.LeftButton:
            # 计算点击了哪个点
            x = event.pos().x()
            clicked_index = x // (self._dot_size + self._dot_spacing)
            
            if 0 <= clicked_index < self._total_pages:
                if clicked_index != self._current_page:
                    self.page_clicked.emit(clicked_index)
