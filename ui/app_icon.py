# -*- coding: utf-8 -*-
"""
应用图标组件
单个应用图标 Widget，包含图标图片和名称标签，带悬停/点击动效。
"""

from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QGraphicsDropShadowEffect, QMenu, QLineEdit
)
from PyQt5.QtGui import (
    QPixmap, QPainter, QPainterPath, QColor, QFont, QFontMetrics,
    QCursor, QDrag
)
from PyQt5.QtCore import (
    Qt, QSize, QPropertyAnimation, pyqtSignal,
    QRectF, QMimeData, QPoint
)

from core.app_scanner import AppInfo


class AppIcon(QWidget):
    """macOS 风格应用图标组件"""

    clicked = pyqtSignal(AppInfo)
    delete_requested = pyqtSignal(AppInfo)
    rename_requested = pyqtSignal(AppInfo, str)
    drag_started = pyqtSignal(AppInfo)
    drag_finished = pyqtSignal(AppInfo)

    def __init__(self, app_info: AppInfo, pixmap: QPixmap = None,
                 icon_size: int = 80, corner_radius: int = 18,
                 label_font_size: int = 12, hide_label: bool = False, parent=None):
        super().__init__(parent)
        self.app_info = app_info
        self._icon_size = icon_size
        self._corner_radius = corner_radius
        self._pixmap = pixmap
        self._scale = 1.0
        self._pressed = False
        self._hover = False
        self._drag_start_pos = QPoint()
        self._hide_label = hide_label

        # 固定组件总大小
        total_w = icon_size + 40  # 120
        total_h = icon_size + 36  # 116
        self.setFixedSize(total_w, total_h)
        self._target_size = QSize(total_w, total_h)

        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setAttribute(Qt.WA_TranslucentBackground)

        # ─── 布局 ─────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        # 图标容器
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(icon_size, icon_size)
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setAttribute(Qt.WA_TranslucentBackground)

        if pixmap and not pixmap.isNull():
            rounded = self._make_rounded_pixmap(pixmap, icon_size, corner_radius)
            self._icon_label.setPixmap(rounded)
        else:
            # 默认图标占位
            fallback = self._create_fallback_pixmap(icon_size)
            self._icon_label.setPixmap(fallback)

        layout.addWidget(self._icon_label, 0, Qt.AlignHCenter)

        # 名称标签
        self._name_label = QLabel(app_info.name)
        self._name_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self._name_label.setFixedWidth(total_w)
        self._name_label.setWordWrap(False)

        # 字体设置 (行楷)
        self.font = QFont("华文行楷", 13)
        self.font.setStyleHint(QFont.Cursive)
        # 兼容备选字体
        self.font.insertSubstitutions("华文行楷", ["行楷", "STXingkai", "KaiTi", "楷体", "Microsoft YaHei"])
        self.font_metrics = QFontMetrics(self.font)
        elided = self.font_metrics.elidedText(app_info.name, Qt.ElideRight, total_w - 4)
        self._name_label.setText(elided)
        self._name_label.setFont(self.font)

        self._name_label.setStyleSheet("""
            color: #FFFFFF;
            background: transparent;
            padding: 0 2px;
        """)

        # 文字阴影效果
        shadow = QGraphicsDropShadowEffect(self._name_label)
        shadow.setBlurRadius(4)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 1)
        self._name_label.setGraphicsEffect(shadow)
        layout.addWidget(self._name_label, 0, Qt.AlignHCenter)
        if hide_label:
            self._name_label.hide()

        # 隐藏的输入框，用于重命名
        self._name_edit = QLineEdit(self.app_info.name)
        self._name_edit.setAlignment(Qt.AlignCenter)
        self._name_edit.setFont(self.font)
        self._name_edit.setStyleSheet("""
            QLineEdit {
                color: #FFFFFF;
                background-color: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.4);
                border-radius: 4px;
                padding: 0 2px;
            }
        """)
        self._name_edit.setFixedWidth(total_w)
        self._name_edit.hide()
        self._name_edit.editingFinished.connect(self._on_rename_finished)
        layout.addWidget(self._name_edit, 0, Qt.AlignHCenter)

        # ─── 状态变量 ─────────────────────────────────
        self._hover_anim = QPropertyAnimation(self, b"windowOpacity")

    def _make_rounded_pixmap(self, pixmap: QPixmap, size: int,
                              radius: int) -> QPixmap:
        """将图标裁剪为圆角矩形（macOS squircle 风格）"""
        scaled = pixmap.scaled(size, size, Qt.KeepAspectRatio,
                                Qt.SmoothTransformation)

        result = QPixmap(size, size)
        result.fill(Qt.transparent)

        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
        painter.setClipPath(path)

        # 居中绘制
        x = (size - scaled.width()) // 2
        y = (size - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.end()

        return result

    def _update_icon_size(self):
        """更新图标大小（实现缩放动画效果）"""
        if self._pressed:
            s = int(self._icon_size * 0.92)
        elif self._hover:
            s = int(self._icon_size * 1.06)
        else:
            s = self._icon_size

        if self._pixmap and not self._pixmap.isNull():
            rounded = self._make_rounded_pixmap(self._pixmap, s, self._corner_radius)
            self._icon_label.setPixmap(rounded)
            self._icon_label.setFixedSize(s, s)
        else:
            fallback = self._create_fallback_pixmap(s)
            self._icon_label.setPixmap(fallback)
            self._icon_label.setFixedSize(s, s)

    def _create_fallback_pixmap(self, size: int) -> QPixmap:
        """为没有图标的应用创建一个带有首字母的彩色占位图标"""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, size, size), self._corner_radius, self._corner_radius)
        painter.setClipPath(path)

        # 简单的背景色 (基于名称长度的伪随机)
        colors = [QColor(231, 76, 60), QColor(46, 204, 113), QColor(52, 152, 219),
                  QColor(155, 89, 182), QColor(241, 196, 15), QColor(230, 126, 34)]
        color = colors[len(self.app_info.name) % len(colors)]
        painter.fillRect(0, 0, size, size, color)

        # 绘制首字母
        first_char = self.app_info.name[0].upper() if self.app_info.name else "?"
        painter.setPen(Qt.white)
        font = QFont("Segoe UI", int(size * 0.4), QFont.Bold)
        painter.setFont(font)
        painter.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, first_char)

        painter.end()
        return pixmap

    # ─── 鼠标事件 ────────────────────────────────────────

    def enterEvent(self, event):
        """悬停进入 - 轻微放大"""
        self._hover = True
        self._update_icon_size()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """悬停离开 - 恢复原大小"""
        self._hover = False
        self._pressed = False
        self._update_icon_size()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """按下 - 缩小效果 或 右键菜单"""
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self._update_icon_size()
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动 - 检测拖拽"""
        if not self._pressed:
            return
        if (event.pos() - self._drag_start_pos).manhattanLength() > 10:
            self._pressed = False
            self._update_icon_size()
            self.drag_started.emit(self.app_info)
            
            # 开始 Qt 拖拽
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(f"app_id:{self.app_info.app_id}")
            drag.setMimeData(mime)
            drag.setPixmap(self.grab())
            drag.setHotSpot(self._drag_start_pos)
            drag.exec_(Qt.MoveAction)
            self.drag_finished.emit(self.app_info)
            
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """释放 - 触发点击"""
        if event.button() == Qt.LeftButton and self._pressed:
            self._pressed = False
            self._update_icon_size()
            if self.rect().contains(event.pos()):
                self.clicked.emit(self.app_info)
        super().mouseReleaseEvent(event)
        
    def contextMenuEvent(self, event):
        """右键菜单 - 删除 / 重命名"""
        menu = QMenu(self)
        menu.setWindowFlags(menu.windowFlags() | Qt.FramelessWindowHint)
        menu.setAttribute(Qt.WA_TranslucentBackground)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(255, 255, 255, 0.75);
                color: #333333;
                border: 1px solid rgba(255, 255, 255, 0.6);
                border-radius: 10px;
                padding: 6px;
                font-family: "Segoe UI", "Microsoft YaHei";
                font-size: 13px;
            }
            QMenu::item {
                padding: 6px 24px;
                border-radius: 6px;
                background-color: transparent;
            }
            QMenu::item:selected {
                background-color: rgba(10, 132, 255, 0.85); /* macOS Accent Blue */
                color: white;
            }
        """)
        rename_action = menu.addAction("重命名...")
        delete_action = menu.addAction("移除应用")
        
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == delete_action:
            self.delete_requested.emit(self.app_info)
        elif action == rename_action:
            self._start_inline_rename()

    def _start_inline_rename(self):
        """开启无感重命名模式"""
        self._name_label.hide()
        self._name_edit.setText(self.app_info.name)
        self._name_edit.show()
        self._name_edit.setFocus()
        self._name_edit.selectAll()

    def _on_rename_finished(self):
        """重命名完成（回车或失去焦点）"""
        self._name_edit.hide()
        if not self._hide_label:
            self._name_label.show()
        new_name = self._name_edit.text().strip()
        if new_name and new_name != self.app_info.name:
            # 仅修改 UI 和发出信号
            self.app_info.name = new_name
            elided = self.font_metrics.elidedText(new_name, Qt.ElideRight, self._name_label.width() - 4)
            self._name_label.setText(elided)
            self.rename_requested.emit(self.app_info, new_name)

    def set_pixmap(self, pixmap: QPixmap):
        """更新图标"""
        self._pixmap = pixmap
        self._update_icon_size()
