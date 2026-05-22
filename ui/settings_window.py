# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, 
    QListWidget, QListWidgetItem, QStackedWidget,
    QWidget, QSlider, QComboBox, QLineEdit, QPushButton
)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtProperty, QPropertyAnimation, QRect, QEasingCurve, QRectF
from PyQt5.QtGui import QPainter, QColor, QPainterPath, QPen

from core.config import Config


class ToggleSwitch(QWidget):
    """苹果风格的拨动开关"""
    toggled = pyqtSignal(bool)

    def __init__(self, parent=None, checked=False):
        super().__init__(parent)
        self.setFixedSize(46, 26)
        self._checked = checked
        self._thumb_x = 24 if checked else 2
        
        self.anim = QPropertyAnimation(self, b"thumb_x")
        self.anim.setDuration(150)
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)

    @pyqtProperty(int)
    def thumb_x(self):
        return self._thumb_x

    @thumb_x.setter
    def thumb_x(self, val):
        self._thumb_x = val
        self.update()

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        if self._checked == checked:
            return
        self._checked = checked
        self.anim.setEndValue(24 if checked else 2)
        self.anim.start()
        self.toggled.emit(self._checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制背景
        bg_color = QColor("#0A84FF") if self._checked else QColor("#39393D")
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), self.height() // 2, self.height() // 2)
        painter.fillPath(path, bg_color)

        # 绘制滑块
        thumb_rect = QRect(self._thumb_x, 2, 22, 22)
        painter.setBrush(Qt.white)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(thumb_rect)


class SettingsWindow(QWidget):
    """MacLaunchpad 设置界面"""
    
    settings_changed = pyqtSignal()  # 当需要主窗口刷新时发射

    def __init__(self, config=None, hotkey_manager=None, parent=None):
        super().__init__(parent)
        self.config = config if config is not None else Config()
        self.hotkey_manager = hotkey_manager
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        self.setWindowTitle("设置 - MacLaunchpad")
        self.setFixedSize(700, 540)
        
        # 内嵌子控件，不需要 FramelessWindowHint 或 Dialog 标志，但需要透明背景支持圆角
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setStyleSheet("background: transparent;")

        # 主布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 侧边栏
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(180)
        self.sidebar.setStyleSheet("""
            QListWidget {
                background: rgba(255, 255, 255, 0.05);
                border: none;
                border-right: 1px solid rgba(255, 255, 255, 0.1);
                outline: none;
                padding-top: 20px;
            }
            QListWidget::item {
                color: rgba(255, 255, 255, 0.8);
                height: 36px;
                padding-left: 20px;
                font-size: 14px;
                border-radius: 6px;
                margin: 4px 12px;
            }
            QListWidget::item:selected {
                background: rgba(255, 255, 255, 0.15);
                color: white;
                font-weight: bold;
            }
            QListWidget::item:hover:!selected {
                background: rgba(255, 255, 255, 0.08);
            }
        """)
        main_layout.addWidget(self.sidebar)

        # 内容区
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet("""
            QWidget { background: transparent; color: white; font-family: "Segoe UI", "Microsoft YaHei"; }
            QLabel { font-size: 13px; }
            QLabel.title { font-size: 22px; font-weight: bold; margin-bottom: 20px; }
        """)
        main_layout.addWidget(self.stacked_widget, 1)

        # 添加页面
        self.add_page("通用", self.create_general_page())
        self.add_page("外观与排版", self.create_appearance_page())
        # self.add_page("关于", self.create_about_page())

        self.sidebar.currentRowChanged.connect(self.stacked_widget.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        # 右上角圆形关闭按钮 ("✕")
        self.close_btn = QPushButton("✕", self)
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                color: rgba(255, 255, 255, 0.5);
                background-color: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 14px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: white;
                background-color: rgba(255, 59, 48, 0.85); /* 苹果红 */
            }
            QPushButton:pressed {
                background-color: rgba(230, 45, 35, 0.9);
            }
        """)
        self.close_btn.move(self.width() - 38, 10)
        self.close_btn.clicked.connect(self.hide_view)

    def paintEvent(self, event):
        """显式绘制半透明底色，确保毛玻璃正确显示"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 为了让窗口有圆角，我们需要绘制一个底板
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 12, 12)
        
        # 填充和控制台一致的半透明白色
        painter.fillPath(path, QColor(255, 255, 255, 60))
        
        # 描边（白色半透明微光）
        pen = QPen(QColor(255, 255, 255, 45))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)

    def add_page(self, title: str, widget: QWidget):
        item = QListWidgetItem(title)
        self.sidebar.addItem(item)
        self.stacked_widget.addWidget(widget)

    def create_card_group(self, title: str, items: list) -> QWidget:
        """创建一个苹果风格的圆角设置卡片组"""
        group = QWidget()
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 20)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 12px; font-weight: bold; padding-left: 5px;")
        layout.addWidget(title_lbl)

        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background: rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(15, 10, 15, 10)
        card_layout.setSpacing(10)

        for i, (label_text, control) in enumerate(items):
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("background: transparent; border: none;")
            row.addWidget(lbl)
            row.addStretch()
            
            # Control could be a widget
            if isinstance(control, QWidget):
                # Ensure control is transparent background
                if not isinstance(control, (QSlider, ToggleSwitch, QComboBox, QLineEdit)):
                    control.setStyleSheet("background: transparent; border: none;")
                row.addWidget(control)
            
            card_layout.addLayout(row)

            # Add divider except for last item
            if i < len(items) - 1:
                div = QWidget()
                div.setFixedHeight(1)
                div.setStyleSheet("background: rgba(255, 255, 255, 0.08); border: none;")
                card_layout.addWidget(div)

        layout.addWidget(card)
        return group

    def create_general_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("通用设置")
        title.setProperty("class", "title")
        layout.addWidget(title)

        # Controls
        self.sw_autostart = ToggleSwitch()
        self.sw_autostart.toggled.connect(self._on_autostart_changed)
        
        self.combo_hotkey = QComboBox()
        self.combo_hotkey.addItems(["ctrl+space", "alt+space", "win+space", "ctrl+shift+space"])
        self.combo_hotkey.setFixedWidth(120)
        self.combo_hotkey.setStyleSheet("""
            QComboBox { background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); border-radius: 4px; padding: 2px 8px; }
            QComboBox::drop-down { border: none; }
        """)
        self.combo_hotkey.currentTextChanged.connect(self._on_hotkey_changed)

        self.sw_pinyin = ToggleSwitch()
        self.sw_pinyin.toggled.connect(lambda v: self.config.set("enable_pinyin_search", v))

        group1 = self.create_card_group("系统", [
            ("开机自启动", self.sw_autostart),
            ("全局呼出快捷键", self.combo_hotkey)
        ])
        
        group2 = self.create_card_group("搜索", [
            ("启用拼音首字母搜索 (需重启生效)", self.sw_pinyin)
        ])

        layout.addWidget(group1)
        layout.addWidget(group2)
        layout.addStretch()

        return page

    def create_appearance_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("外观与排版")
        title.setProperty("class", "title")
        layout.addWidget(title)

        # Helpers
        def make_slider(min_v, max_v, config_key, step=1):
            slider = QSlider(Qt.Horizontal)
            slider.setRange(min_v, max_v)
            slider.setSingleStep(step)
            slider.setFixedWidth(150)
            slider.setStyleSheet("""
                QSlider::groove:horizontal { border-radius: 2px; height: 4px; background: rgba(255,255,255,0.2); }
                QSlider::handle:horizontal { background: #FFFFFF; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }
                QSlider::sub-page:horizontal { background: #0A84FF; border-radius: 2px; }
            """)
            lbl_val = QLabel("0")
            lbl_val.setFixedWidth(30)
            
            h_layout = QHBoxLayout()
            h_layout.addWidget(slider)
            h_layout.addWidget(lbl_val)
            h_layout.setContentsMargins(0,0,0,0)
            container = QWidget()
            container.setLayout(h_layout)
            container.setStyleSheet("background: transparent; border: none;")

            def on_change(val):
                lbl_val.setText(str(val))
                self.config.set(config_key, val)
                self.settings_changed.emit() # 实时刷新主网格

            slider.valueChanged.connect(on_change)
            return container, slider, lbl_val

        c1, self.sl_cols, self.lbl_cols = make_slider(3, 12, "grid_columns")
        c2, self.sl_rows, self.lbl_rows = make_slider(2, 8, "grid_rows")
        c3, self.sl_icon, self.lbl_icon = make_slider(40, 150, "icon_size")
        c4, self.sl_font, self.lbl_font = make_slider(8, 24, "icon_label_font_size")
        c5, self.sl_folder_bg, self.lbl_folder_bg = make_slider(10, 150, "folder_bg_opacity")

        self.sw_hide_labels = ToggleSwitch()
        self.sw_hide_labels.toggled.connect(self._on_hide_labels_changed)

        group1 = self.create_card_group("网格排版", [
            ("每页列数", c1),
            ("每页行数", c2)
        ])

        group2 = self.create_card_group("图标", [
            ("图标大小", c3),
            ("字体大小", c4),
            ("隐藏图标名称", self.sw_hide_labels)
        ])

        group3 = self.create_card_group("文件夹", [
            ("文件夹背景亮度", c5)
        ])

        layout.addWidget(group1)
        layout.addWidget(group2)
        layout.addWidget(group3)
        layout.addStretch()

        return page

    def load_settings(self):
        """将配置加载到 UI"""
        c = self.config
        
        # General
        self.sw_autostart.setChecked(c.get("auto_start", False))
        self.sw_hide_labels.setChecked(c.get("hide_icon_labels", False))
        
        hotkey = c.get("hotkey", "ctrl+space")
        idx = self.combo_hotkey.findText(hotkey)
        if idx >= 0:
            self.combo_hotkey.setCurrentIndex(idx)
        else:
            self.combo_hotkey.addItem(hotkey)
            self.combo_hotkey.setCurrentText(hotkey)
            
        self.sw_pinyin.setChecked(c.get("enable_pinyin_search", True))

        # Appearance
        def set_sl(sl, lbl, val):
            sl.blockSignals(True)
            sl.setValue(val)
            lbl.setText(str(val))
            sl.blockSignals(False)

        set_sl(self.sl_cols, self.lbl_cols, c.get("grid_columns"))
        set_sl(self.sl_rows, self.lbl_rows, c.get("grid_rows"))
        set_sl(self.sl_icon, self.lbl_icon, c.get("icon_size"))
        set_sl(self.sl_font, self.lbl_font, c.get("icon_label_font_size"))
        set_sl(self.sl_folder_bg, self.lbl_folder_bg, c.get("folder_bg_opacity", 40))

    def _on_autostart_changed(self, checked):
        self.config.set_auto_start(checked)

    def _on_hide_labels_changed(self, checked):
        self.config.set("hide_icon_labels", checked)
        self.settings_changed.emit()

    def _on_hotkey_changed(self, text):
        self.config.set("hotkey", text)
        if self.hotkey_manager:
            try:
                self.hotkey_manager.update_hotkey(text)
                print(f"[Settings] 成功重新注册快捷键: {text}")
            except Exception as e:
                print(f"[Settings] 重新注册快捷键失败: {e}")

    def show_view(self):
        import time
        self._show_time = time.time()
        if self.parent():
            p_size = self.parent().size()
            self.setGeometry(
                (p_size.width() - 700) // 2,
                (p_size.height() - 540) // 2,
                700, 540
            )
        self.show()
        self.raise_()
        self.setFocus()

    def hide_view(self):
        self.hide()

    def mousePressEvent(self, event):
        """支持在父窗口内拖动内嵌设置卡片"""
        if event.button() == Qt.LeftButton and event.y() < 50:
            self._is_dragging = True
            self._drag_start_pos = event.pos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if hasattr(self, '_is_dragging') and self._is_dragging:
            # 相对于父窗口的移动位置
            target_pos = self.mapToParent(event.pos()) - self._drag_start_pos
            # 限制拖拽不要完全超出父窗口边界
            if self.parent():
                pw, ph = self.parent().width(), self.parent().height()
                target_pos.setX(max(-350, min(pw - 350, target_pos.x())))
                target_pos.setY(max(0, min(ph - 50, target_pos.y())))
            self.move(target_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._is_dragging = False
        super().mouseReleaseEvent(event)

