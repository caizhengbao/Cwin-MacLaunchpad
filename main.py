# -*- coding: utf-8 -*-
"""
MacLaunchpad for Windows
入口文件，管理应用生命周期、系统托盘和子系统初始化。
"""

import sys
import ctypes
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from core.config import Config
from core.app_scanner import AppScanner
from core.icon_cache import IconCache
from core.hotkey_manager import HotkeyManager
from ui.launchpad_window import LaunchpadWindow


def setup_dpi_awareness():
    """配置高 DPI 适配"""
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2) # PROCESS_PER_MONITOR_DPI_AWARE
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception as e:
                print(f"[Main] 设置高DPI感知失败: {e}")


class LaunchpadApp:
    def __init__(self):
        # 初始化核心组件
        self.config = Config()
        self.config.load()
        
        self.icon_cache = IconCache(icon_size=self.config.get("icon_size", 80))
        self.scanner = AppScanner()
        
        # UI 组件
        self.window = LaunchpadWindow(self.config, self.scanner, self.icon_cache)
        
        # 快捷键管理
        self.hotkey_manager = HotkeyManager()
        self.hotkey_manager.hotkey_triggered.connect(self.toggle_launchpad)
        self.hotkey_manager.register(self.config.get("hotkey", "ctrl+space"))
        
        # 注入快捷键管理器给主窗口，并绑定设置变更信号
        self.window.set_hotkey_manager(self.hotkey_manager)
        self.window.settings_changed.connect(self.on_settings_changed)
        
        # 监听窗口菜单事件 (替代托盘功能)
        self.window.show_settings_requested.connect(self.show_settings)
        self.window.quit_requested.connect(self.quit_app)

    def toggle_launchpad(self):
        if self.window.isVisible():
            self.hide_launchpad()
        else:
            self.show_launchpad()

    def show_launchpad(self):
        self.window.show_launchpad()

    def hide_launchpad(self):
        self.window.hide_launchpad()

    def show_settings(self):
        self.window.show_settings()

    def on_settings_changed(self):
        """当设置参数改变时实时重新渲染网格"""
        self.window.app_grid.cols = self.config.get("grid_columns", 7)
        self.window.app_grid.rows = self.config.get("grid_rows", 5)
        self.window.app_grid.spacing_h = self.config.get("icon_spacing_h", 130)
        self.window.app_grid.spacing_v = self.config.get("icon_spacing_v", 130)
        
        # 刷新图标尺寸
        new_icon_size = self.config.get("icon_size", 80)
        self.icon_cache.icon_size = new_icon_size
        self.icon_cache.extractor.target_size = new_icon_size
        self.icon_cache.clear_memory_cache()
        
        # 重新加载和排版
        self.window.load_apps()
        self.window.app_grid._container.update()
        self.window.app_grid.update()

        # 实时重绘当前可见的文件夹展开视图，使用户拉动亮度滑块时能立刻看到不透明度变化
        if hasattr(self.window, "_folder_view") and self.window._folder_view is not None:
            try:
                if self.window._folder_view.isVisible():
                    self.window._folder_view.update()
            except Exception:
                pass

    def quit_app(self):
        self.hotkey_manager.unregister()
        QApplication.quit()


def main():
    setup_dpi_awareness()
    
    # 启用高 DPI 缩放
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 保持后台运行
    
    # 防止多开
    import win32event
    import win32api
    import winerror
    
    global_mutex = win32event.CreateMutex(None, 1, "MacLaunchpad_SingleInstance_Mutex")
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        print("Application is already running.")
        sys.exit(0)
        
    _app_instance = LaunchpadApp()
    
    # 保持 mutex 的引用，防止被垃圾回收
    sys._mac_launchpad_mutex = global_mutex
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
