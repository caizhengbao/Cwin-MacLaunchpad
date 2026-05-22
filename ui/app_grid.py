# -*- coding: utf-8 -*-
"""
应用网格布局与分页管理模块
应用网格与分页管理模块
负责将应用图标排列为多页网格，并支持滑动切换。
"""

import math
from typing import List

from PyQt5.QtWidgets import QWidget, QLabel, QMenu, QFileDialog
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QRectF, pyqtSignal, QTimer
from PyQt5.QtGui import QPainter, QColor, QPainterPath, QPen, QPixmap

from core.app_scanner import AppInfo
from .app_icon import AppIcon
from .animations import AnimationManager

try:
    import pypinyin
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False

class GridContainer(QWidget):
    """用于承载所有页面的容器，同时负责绘制每一页的背景方框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.app_grid = parent
        self.draw_background = getattr(parent, 'draw_background', True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 确保有 app_grid 引用及分页数量
        if not hasattr(self.app_grid, 'total_pages'):
            return

        if not self.draw_background:
            return

        grid_w = self.app_grid.cols * self.app_grid.spacing_h
        grid_h = self.app_grid.rows * self.app_grid.spacing_v
        page_width = self.app_grid.width()
        page_height = self.app_grid.height()

        offset_x = (page_width - grid_w) / 2.0
        offset_y = (page_height - grid_h) / 2.0
        padding = 10
        
        # 给每一页画一个圆角框
        for p in range(max(1, self.app_grid.total_pages)):
            px = p * page_width + offset_x - padding
            py = offset_y - padding
            rect = QRectF(px, py, grid_w + padding * 2, grid_h + padding * 2)
            
            path = QPainterPath()
            path.addRoundedRect(rect, 24, 24)
            
            # 半透明白色填充
            painter.fillPath(path, QColor(255, 255, 255, 40))
            
            # 外部描边
            pen = QPen(QColor(255, 255, 255, 40))
            pen.setWidthF(1.5)
            painter.setPen(pen)
            painter.drawPath(path)


class AppGrid(QWidget):
    """应用网格视图，支持多页显示与平滑滚动"""
    
    # 点击空白处触发隐藏
    clicked_outside = pyqtSignal()
    
    # 图标级事件向外透传
    icon_clicked = pyqtSignal(AppInfo)
    icon_delete_requested = pyqtSignal(AppInfo)
    icon_drag_started = pyqtSignal(AppInfo)
    icon_drag_finished = pyqtSignal(AppInfo)
    icon_rename_requested = pyqtSignal(AppInfo, str)
    folder_opened = pyqtSignal(AppInfo)

    def __init__(self, config, icon_cache, animation_manager: AnimationManager, scanner, parent=None, draw_background=True):
        super().__init__(parent)
        self.config = config
        self.draw_background = draw_background
        self.icon_cache = icon_cache
        self.anim_manager = animation_manager
        self.scanner = scanner

        # 配置参数
        self.cols = self.config.get("grid_columns", 8)
        self.rows = self.config.get("grid_rows", 4)
        self.spacing_h = self.config.get("icon_spacing_h", 130)
        self.spacing_v = self.config.get("icon_spacing_v", 130)
        
        self.apps: List[AppInfo] = []
        self.filtered_apps: List[AppInfo] = []
        self.icon_widgets: List[AppIcon] = []
        
        self.current_page = 0
        self.total_pages = 1
        
        # 滑动动画
        self._slide_anim = None
        
        # 内部容器，包含所有的页
        self._container = GridContainer(self)
        self._container.move(0, 0)
        
        # 空提示标签
        self._empty_label = QLabel("没有找到应用", self)
        self._empty_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 18px;")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.hide()

    def set_apps(self, apps: List[AppInfo]):
        """设置要显示的应用列表"""
        self.apps = apps
        self.filtered_apps = list(apps)
        self._rebuild_grid()

    def filter_apps(self, query: str):
        """过滤应用列表（支持拼音）"""
        if not query:
            self.filtered_apps = list(self.apps)
        else:
            query = query.lower()
            filtered = []
            
            enable_pinyin = self.config.get("enable_pinyin_search", True) and HAS_PYPINYIN
            
            # 获取所有具体的应用（排除文件夹本身，搜寻范围包括文件夹内的应用）
            all_apps = [a for a in self.scanner.apps if not a.is_folder]
            
            for app in all_apps:
                name_lower = app.name.lower()
                match = False
                
                # 1. 直接匹配
                if query in name_lower:
                    match = True
                # 2. 拼音首字母匹配
                elif enable_pinyin:
                    pinyin_list = pypinyin.lazy_pinyin(app.name, style=pypinyin.Style.FIRST_LETTER)
                    pinyin_str = "".join(pinyin_list).lower()
                    if query in pinyin_str:
                        match = True
                
                if match:
                    filtered.append(app)
            
            # 为过滤后的应用赋予自增的临时虚拟 grid_index，使得它们可以在第一页连续排列
            from dataclasses import replace
            self.filtered_apps = []
            for i, app in enumerate(filtered):
                self.filtered_apps.append(replace(app, grid_index=i))

        self._rebuild_grid()
        self.switch_to_page(0, animate=False)

    def _rebuild_grid(self):
        """重新构建网格布局"""
        # 清除旧图标
        for icon in self.icon_widgets:
            icon.setParent(None)
            icon.deleteLater()
        self.icon_widgets.clear()

        apps_per_page = self.rows * self.cols
        if not self.filtered_apps:
            self.total_pages = 1
        else:
            max_index = max(a.grid_index for a in self.filtered_apps)
            self.total_pages = max(1, math.ceil((max_index + 1) / apps_per_page))

        num_apps = len(self.filtered_apps)
        if num_apps == 0:
            self._empty_label.show()
            self._empty_label.setGeometry(self.rect())
        else:
            self._empty_label.hide()

        # 根据当前控件大小计算一页的大小和起始位置
        page_width = self.width()
        page_height = self.height()
        
        self._container.resize(page_width * self.total_pages, page_height)
        
        # 计算网格整体宽度和高度，用于居中
        grid_w = self.cols * self.spacing_h
        grid_h = self.rows * self.spacing_v
        
        offset_x = (page_width - grid_w) // 2
        offset_y = (page_height - grid_h) // 2
        
        for app in self.filtered_apps:
            idx = getattr(app, "grid_index", -1)
            if idx < 0:
                continue # 防御性编程，理论上都有
                
            page_index = idx // apps_per_page
            idx_in_page = idx % apps_per_page
            row = idx_in_page // self.cols
            col = idx_in_page % self.cols

            if getattr(app, "is_folder", False):
                pixmap = self._generate_folder_icon(app)
            else:
                pixmap = self.icon_cache.get_icon(app)

            icon_widget = AppIcon(
                app, 
                pixmap=pixmap,
                icon_size=self.config.get("icon_size", 64),
                corner_radius=self.config.get("icon_corner_radius", 18),
                label_font_size=self.config.get("icon_label_font_size", 12),
                hide_label=self.config.get("hide_icon_labels", False),
                parent=self._container
            )
            
            # 透传子组件事件
            icon_widget.clicked.connect(self._handle_icon_click)
            icon_widget.delete_requested.connect(self.icon_delete_requested.emit)
            icon_widget.drag_started.connect(self.icon_drag_started.emit)
            icon_widget.drag_finished.connect(self.icon_drag_finished.emit)
            icon_widget.rename_requested.connect(self.icon_rename_requested.emit)
            
            # 居中对齐图标
            cx = page_index * page_width + offset_x + col * self.spacing_h + (self.spacing_h // 2)
            cy = offset_y + row * self.spacing_v + (self.spacing_v // 2)
            
            icon_widget.move(int(cx - icon_widget.width() // 2), int(cy - icon_widget.height() // 2))
            icon_widget.show()
            self.icon_widgets.append(icon_widget)

        # 限制当前页并重新更新容器位置与重绘
        self.current_page = max(0, min(self.total_pages - 1, self.current_page))
        self.switch_to_page(self.current_page, animate=False)
        self._container.update()
        self.update()

    def _handle_icon_click(self, app_info):
        """处理内部图标点击"""
        if getattr(app_info, "is_folder", False):
            self.folder_opened.emit(app_info)
        else:
            self.icon_clicked.emit(app_info)

    def resizeEvent(self, event):
        """窗口大小改变时重新布局"""
        super().resizeEvent(event)
        self._rebuild_grid()
        self.switch_to_page(self.current_page, animate=False)

    def _generate_folder_icon(self, folder_app) -> QPixmap:
        """生成九宫格缩微文件夹图标"""
        size = self.config.get("icon_size", 64)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        
        # 绘制文件夹半透明底板
        path = QPainterPath()
        radius = self.config.get("icon_corner_radius", 18)
        path.addRoundedRect(0, 0, size, size, radius, radius)
        painter.fillPath(path, QColor(255, 255, 255, 60))
        
        # 绘制缩微图标 (3x3 九宫格)
        padding = size * 0.15
        inner_size = size - padding * 2
        mini_size = inner_size / 3.0
        
        # 按照 children_ids 中的实际物理顺序（过滤空占位）显示前 9 个应用预览
        non_empty_ids = [cid for cid in folder_app.children_ids if cid]
        children = []
        for cid in non_empty_ids[:9]:
            child_app = self.scanner._get_app(cid)
            if child_app:
                children.append(child_app)
        
        for i, child_app in enumerate(children):
            row = i // 3
            col = i % 3
            cx = padding + col * mini_size + mini_size / 2
            cy = padding + row * mini_size + mini_size / 2
            
            child_pix = self.icon_cache.get_icon(child_app)
            if child_pix and not child_pix.isNull():
                mini_pix = child_pix.scaled(int(mini_size * 0.8), int(mini_size * 0.8), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                painter.drawPixmap(int(cx - mini_pix.width() / 2), int(cy - mini_pix.height() / 2), mini_pix)
                
        painter.end()
        return pixmap

    def mousePressEvent(self, event):
        """检测点击是否在网格面板外部"""
        if event.button() == Qt.LeftButton:
            grid_w = self.cols * self.spacing_h
            grid_h = self.rows * self.spacing_v
            offset_x = (self.width() - grid_w) / 2.0
            offset_y = (self.height() - grid_h) / 2.0
            padding = 10
            rect = QRectF(offset_x - padding, offset_y - padding, grid_w + padding * 2, grid_h + padding * 2)
            
            if not rect.contains(event.pos()):
                self.clicked_outside.emit()
        super().mousePressEvent(event)

    def switch_to_page(self, page_index: int, animate: bool = True):
        """切换到指定页"""
        if page_index < 0:
            page_index = 0
        if page_index >= self.total_pages:
            page_index = self.total_pages - 1

        self.current_page = page_index
        target_x = -(page_index * self.width())

        if self._slide_anim:
            self._slide_anim.stop()

        if animate:
            self._slide_anim = QPropertyAnimation(self._container, b"pos")
            self._slide_anim.setDuration(self.config.get("anim_page_switch_duration", 400))
            self._slide_anim.setStartValue(self._container.pos())
            self._slide_anim.setEndValue(QPoint(target_x, 0))
            self._slide_anim.setEasingCurve(QEasingCurve.InOutCubic)
            self._slide_anim.start()
        else:
            self._container.move(target_x, 0)
            
    def get_all_icons(self) -> List[AppIcon]:
        """获取当前显示的所有图标控件（用于动画）"""
        return self.icon_widgets

    def get_index_at_pos(self, pos: QPoint) -> int:
        """根据坐标计算对应在网格中的绝对索引位置（支持空白网格点）"""
        page_width = self.width()
        page_height = self.height()
        
        # 将局部坐标转换为全局滚动坐标
        global_x = pos.x() + self.current_page * page_width
        
        grid_w = self.cols * self.spacing_h
        grid_h = self.rows * self.spacing_v
        
        offset_x = (page_width - grid_w) // 2
        offset_y = (page_height - grid_h) // 2

        # 判断在哪一页
        page = global_x // page_width
        
        # 当前页内部的相对 x
        local_x = global_x % page_width - offset_x
        local_y = pos.y() - offset_y
        
        if 0 <= local_x <= grid_w and 0 <= local_y <= grid_h:
            col = int(local_x // self.spacing_h)
            row = int(local_y // self.spacing_v)
            return int(page * (self.rows * self.cols) + row * self.cols + col)
            
        return -1

    def contextMenuEvent(self, event):
        """右键菜单：添加应用 / 打开设置"""
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
        
        add_action = menu.addAction("添加应用 (.exe / .lnk)")
        settings_action = menu.addAction("设置")
        
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == add_action:
            file_paths, _ = QFileDialog.getOpenFileNames(
                self, 
                "选择要添加的应用或快捷方式", 
                "", 
                "应用文件 (*.exe *.lnk)"
            )
            if file_paths:
                # 依赖于父窗口的方法来重新加载
                added = False
                # 注意：self.parent() 是 _container 的 parent，而AppGrid的parent是LaunchpadWindow
                main_window = self.window()
                for path in file_paths:
                    if main_window.scanner.add_from_file(path):
                        added = True
                if added:
                    main_window.load_apps()
        elif action == settings_action:
            main_window = self.window()
            main_window.show_settings()
