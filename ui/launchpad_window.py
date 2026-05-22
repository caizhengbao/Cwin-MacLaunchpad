# -*- coding: utf-8 -*-
"""
Launchpad 主窗口
全屏无边框窗口，整合毛玻璃效果、搜索栏、应用网格、动画和交互逻辑。
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QApplication, QMenu
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QEvent
from PyQt5.QtGui import QKeyEvent, QWheelEvent, QPainter, QColor

from core.app_scanner import AppScanner, AppInfo
from core.icon_cache import IconCache
from .blur_effect import apply_blur_to_window
from .search_bar import SearchBar
from .page_indicator import PageIndicator
from .app_grid import AppGrid
from .animations import AnimationManager
from ui.folder_view import FolderView
from .settings_window import SettingsWindow

class LaunchpadWindow(QWidget):
    """主启动器窗口 (全屏、无边框、毛玻璃背景)"""
    
    closed = pyqtSignal()
    show_settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    settings_changed = pyqtSignal()

    def __init__(self, config, app_scanner: AppScanner, icon_cache: IconCache):
        super().__init__()
        self.config = config
        self.scanner = app_scanner
        self.icon_cache = icon_cache
        self.anim_manager = AnimationManager(self.config)
        self._is_closing = False
        
        self.init_ui()
        self.load_apps()

    def set_hotkey_manager(self, hotkey_manager):
        self.hotkey_manager = hotkey_manager
        # 实例化内嵌设置 Widget，以 self 为 parent
        self.settings_widget = SettingsWindow(self.config, self.hotkey_manager, self)
        # 连接 settings_widget.settings_changed 到 self.settings_changed 信号
        self.settings_widget.settings_changed.connect(self.settings_changed.emit)
        self.settings_widget.hide()

    def show_settings(self):
        if hasattr(self, 'settings_widget'):
            self.settings_widget.show_view()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 保持设置界面在主窗口中居中
        if hasattr(self, 'settings_widget') and self.settings_widget.isVisible():
            p_size = self.size()
            self.settings_widget.setGeometry(
                (p_size.width() - 700) // 2,
                (p_size.height() - 540) // 2,
                700, 540
            )

    def init_ui(self):
        """初始化 UI"""
        # 窗口无边框、置顶、透明
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True) # 防止系统绘制不透明背景
        self.setStyleSheet("background: transparent;")
        self.setAcceptDrops(True)
        
        # 尝试应用底层毛玻璃
        apply_blur_to_window(self)
        self._setup_layout()

    def _setup_layout(self):
        # 布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 40, 0, 40)
        main_layout.setSpacing(20)

        # 搜索栏 (顶部居中)
        search_layout = QHBoxLayout()
        self.search_bar = SearchBar(
            width=self.config.get("search_bar_width", 260),
            height=self.config.get("search_bar_height", 36),
            parent=self
        )
        self.search_bar.text_changed.connect(self._on_search_text_changed)
        search_layout.addStretch()
        search_layout.addWidget(self.search_bar)
        search_layout.addStretch()
        main_layout.addLayout(search_layout)

        # 应用网格
        self.app_grid = AppGrid(self.config, self.icon_cache, self.anim_manager, self.scanner, self)
        self.app_grid.clicked_outside.connect(self.hide_launchpad)
        main_layout.addWidget(self.app_grid, 1)

        # 页面指示点 (底部居中)
        indicator_layout = QHBoxLayout()
        self.page_indicator = PageIndicator(self)
        self.page_indicator.page_clicked.connect(self._on_page_clicked)
        indicator_layout.addStretch()
        indicator_layout.addWidget(self.page_indicator)
        indicator_layout.addStretch()
        main_layout.addLayout(indicator_layout)

        # 监听来自 AppGrid 透传的事件
        self.app_grid.icon_clicked.connect(self._on_app_clicked)
        self.app_grid.icon_delete_requested.connect(self._on_app_deleted)
        self.app_grid.icon_rename_requested.connect(self._on_app_renamed)
        self.app_grid.folder_opened.connect(self._on_app_clicked) # 内部 _on_app_clicked 已经处理了 is_folder
        
        # 安装事件过滤器，用于处理全局点击
        self.installEventFilter(self)

    def load_apps(self):
        """加载应用并重置状态"""
        apps = self.scanner.scan_all()
        # 仅显示放置在主网格上的应用/文件夹
        visible_apps = [a for a in apps if a.grid_index >= 0]
        self.app_grid.set_apps(visible_apps)
        self._update_page_indicator()

    def _update_page_indicator(self):
        self.page_indicator.set_pages(self.app_grid.total_pages, self.app_grid.current_page)

    def show_launchpad(self):
        """显示 Launchpad 并播放动画"""
        if self.isVisible() and not self._is_closing:
            return

        self._is_closing = False
        
        # 每次显示前重新加载应用列表以获取最新变化
        self.load_apps()
        self.search_bar.clear()
        
        # 全屏显示
        self.showFullScreen()
        
        # 播放打开动画
        self.anim_manager.stop_all()
        open_anim = self.anim_manager.create_open_animation(
            self, 
            self.app_grid.get_all_icons(),
            self.search_bar
        )
        open_anim.start()
        
        self.setFocus()

    def hide_launchpad(self):
        """播放关闭动画并隐藏"""
        if self._is_closing or not self.isVisible():
            return

        self._is_closing = True
        self.search_bar.clearFocus()
        
        # 显式隐藏设置面板，防止下次打开时它还显示
        if hasattr(self, 'settings_widget'):
            self.settings_widget.hide()
        
        # 播放关闭动画
        self.anim_manager.stop_all()
        close_anim = self.anim_manager.create_close_animation(
            self, 
            self.app_grid.get_all_icons(),
            self.search_bar
        )
        
        # 动画结束后隐藏窗口并发送信号
        close_anim.finished.connect(self._on_close_anim_finished)
        close_anim.start()

    def _on_close_anim_finished(self):
        self.hide()
        self._is_closing = False
        self.closed.emit()

    def paintEvent(self, event):
        """完全透明的背景绘制，将模糊交还给底层 DWM"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 保持极端透明以让底层 DWM Blur 显示
        color = QColor(255, 255, 255, 1) # 极度透明白
        painter.fillRect(self.rect(), color)

    # ─── 交互事件处理 ──────────────────────────────────

    def _on_app_clicked(self, app_info: AppInfo):
        """应用被点击"""
        if getattr(app_info, "is_folder", False):
            # 打开文件夹视图
            self._folder_view = FolderView(self, app_info)
            self._folder_view.show_view()
        else:
            self.hide_launchpad()
            QTimer.singleShot(200, lambda: self.scanner.launch_app(app_info))

    def _on_app_deleted(self, app_info: AppInfo):
        """右键移除应用"""
        self.scanner.remove_app(app_info.app_id)
        self.load_apps()

    def _on_app_renamed(self, app_info: AppInfo, new_name: str):
        """右键重命名应用"""
        self.scanner.update_app_details(app_info.app_id, new_name=new_name)
        self.load_apps()

    def _on_search_text_changed(self, text: str):
        """搜索过滤"""
        self.app_grid.filter_apps(text)
        self._update_page_indicator()
        
        # 重新绑定事件
        for icon_widget in self.app_grid.get_all_icons():
            try:
                icon_widget.clicked.disconnect()
                icon_widget.delete_requested.disconnect()
                icon_widget.rename_requested.disconnect()
            except TypeError:
                pass
            icon_widget.clicked.connect(self._on_app_clicked)
            icon_widget.delete_requested.connect(self._on_app_deleted)
            icon_widget.rename_requested.connect(self._on_app_renamed)

    def _on_page_clicked(self, page_index: int):
        """点击页码指示点"""
        self.app_grid.switch_to_page(page_index)
        self._update_page_indicator()

    def wheelEvent(self, event: QWheelEvent):
        """滚轮切换页面"""
        if self.app_grid.total_pages <= 1:
            return
            
        delta = event.angleDelta().y()
        if delta < 0:  # 向下滚 -> 下一页
            new_page = min(self.app_grid.total_pages - 1, self.app_grid.current_page + 1)
        else:          # 向上滚 -> 上一页
            new_page = max(0, self.app_grid.current_page - 1)
            
        if new_page != self.app_grid.current_page:
            self.app_grid.switch_to_page(new_page)
            self._update_page_indicator()

    def keyPressEvent(self, event: QKeyEvent):
        """按键处理"""
        if event.key() == Qt.Key_Escape:
            self.hide_launchpad()
        elif event.key() == Qt.Key_Left:
            new_page = max(0, self.app_grid.current_page - 1)
            self.app_grid.switch_to_page(new_page)
            self._update_page_indicator()
        elif event.key() == Qt.Key_Right:
            new_page = min(self.app_grid.total_pages - 1, self.app_grid.current_page + 1)
            self.app_grid.switch_to_page(new_page)
            self._update_page_indicator()
        else:
            # 输入字母自动对焦到搜索栏
            if not self.search_bar.has_focus() and event.text().isprintable():
                self.search_bar.focus_input()
                # 将字符传给搜索栏
                QApplication.sendEvent(self.search_bar._input, event)

    def eventFilter(self, obj, event):
        """拦截全局点击，点击空白处关闭"""
        if event.type() == QEvent.MouseButtonPress and obj is self:
            # 去除当前任何子控件的焦点 (如命名输入框)
            self.setFocus()
            
            # 检查是否点击了子控件 (图标或搜索栏等)
            child = self.childAt(event.pos())
            if child is None or child is self:
                # 防误触：如果设置界面显示，点击外部只隐藏设置界面
                if hasattr(self, 'settings_widget') and self.settings_widget.isVisible():
                    import time
                    # 刚显示 200ms 内不响应隐藏，防止右键菜单点击事件穿透导致闪隐
                    if not hasattr(self.settings_widget, '_show_time') or time.time() - self.settings_widget._show_time > 0.2:
                        self.settings_widget.hide()
                    return True
                self.hide_launchpad()
                return True
        return super().eventFilter(obj, event)

    # ─── 外部文件拖拽支持 (添加应用) ──────────────────────

    def dragEnterEvent(self, event):
        """外部文件拖入或内部重排拖入"""
        if event.mimeData().hasUrls() or (event.mimeData().hasText() and event.mimeData().text().startswith("app_id:")):
            event.acceptProposedAction()
        else:
            event.ignore()

    def contextMenuEvent(self, event):
        """右键菜单 - 用于呼出设置和退出（因为取消了托盘图标）"""
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
        
        settings_action = menu.addAction("设置...")
        quit_action = menu.addAction("完全退出")
        
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == settings_action:
            self.show_settings_requested.emit()
        elif action == quit_action:
            self.quit_requested.emit()
            
    def dropEvent(self, event):
        """文件放下或内部排序放下"""
        if event.mimeData().hasUrls():
            self._handle_external_drop(event)
        elif event.mimeData().hasText() and event.mimeData().text().startswith("app_id:"):
            self._handle_internal_drop(event)

    def _handle_external_drop(self, event):
        added = any(self.scanner.add_from_file(url.toLocalFile()) for url in event.mimeData().urls())
        if added:
            self.load_apps()
            event.acceptProposedAction()
        else:
            event.ignore()

    def _handle_internal_drop(self, event):
        app_id = event.mimeData().text().split(":")[1]
        target_index = self.app_grid.get_index_at_pos(self.app_grid.mapFromParent(event.pos()))
        
        if target_index != -1 and not self.search_bar.text():
            target_app = next((a for a in self.scanner.apps if a.grid_index == target_index and a.app_id != app_id), None)
            if target_app:
                if target_app.is_folder:
                    self.scanner.add_to_folder(target_app.app_id, app_id)
                else:
                    self.scanner.create_folder("未命名文件夹", target_app.app_id, app_id)
            else:
                self.scanner.update_app_details(app_id, new_grid_index=target_index)
            self.load_apps()
        event.acceptProposedAction()
