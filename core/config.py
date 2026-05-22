# -*- coding: utf-8 -*-
"""
配置管理模块
负责所有用户可配置项的读写与默认值管理，使用 JSON 持久化。
"""

import json
import os
import sys
from pathlib import Path


def get_app_data_dir() -> Path:
    """获取应用数据目录"""
    base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    app_dir = base / "MacLaunchpad"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_cache_dir() -> Path:
    """获取图标缓存目录"""
    cache_dir = get_app_data_dir() / "cache" / "icons"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


# ─── 默认配置 ───────────────────────────────────────────────

DEFAULT_CONFIG = {
    # 快捷键
    "hotkey": "ctrl+space",

    # 外观
    "icon_size": 80,
    "grid_columns": 7,
    "grid_rows": 5,
    "icon_label_font_size": 12,
    "icon_spacing_h": 130,
    "icon_spacing_v": 130,
    "icon_corner_radius": 18,
    "hide_icon_labels": False,
    "folder_bg_opacity": 40,

    # 搜索
    "search_bar_width": 260,
    "search_bar_height": 36,
    "enable_pinyin_search": True,

    # 动画时长 (ms)
    "anim_open_bg_duration": 300,
    "anim_open_icon_duration": 350,
    "anim_open_icon_stagger": 15,
    "anim_close_icon_duration": 250,
    "anim_close_bg_duration": 200,
    "anim_page_switch_duration": 400,
    "anim_hover_duration": 150,

    # 颜色 (RGBA 字符串)
    "bg_overlay_color": "rgba(30, 30, 30, 0.65)",
    "search_bar_bg": "rgba(255, 255, 255, 0.12)",
    "search_bar_border": "rgba(255, 255, 255, 0.18)",
    "search_bar_text": "rgba(255, 255, 255, 0.85)",
    "search_bar_placeholder": "rgba(255, 255, 255, 0.45)",
    "icon_label_color": "#FFFFFF",
    "page_dot_active": "#FFFFFF",
    "page_dot_inactive": "rgba(255, 255, 255, 0.35)",

    # 扫描路径（额外添加的自定义路径）
    "extra_scan_paths": [],
    # 排除关键词
    "exclude_keywords": [
        "Uninstall", "uninstall", "卸载",
        "Help", "help", "帮助",
        "README", "readme",
        "Documentation", "License", "license",
    ],

    # 系统行为
    "auto_start": False,
    "pause_on_fullscreen": True,
    "minimize_memory_on_idle": True,
    "idle_timeout_seconds": 60,

    # 持久化 - 用户自定义排列（app_id -> position）
    "app_layout": {},
    # 持久化 - 隐藏的应用列表
    "hidden_apps": [],
}


class Config:
    """配置管理器 - 单例模式"""

    _instance = None
    _config_path = get_app_data_dir() / "config.json"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._data = {}
            cls._instance._loaded = False
        return cls._instance

    def load(self):
        """从文件加载配置，如果不存在则使用默认值"""
        self._data = dict(DEFAULT_CONFIG)
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                # 合并：已保存的值覆盖默认值
                self._data.update(saved)
            except (json.JSONDecodeError, IOError):
                pass  # 文件损坏，使用默认值
        self._loaded = True

    def save(self):
        """保存配置到文件"""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"[Config] 保存配置失败: {e}")

    def get(self, key: str, default=None):
        """获取配置值"""
        if not self._loaded:
            self.load()
        return self._data.get(key, default if default is not None else DEFAULT_CONFIG.get(key))

    def set(self, key: str, value):
        """设置配置值并保存"""
        if not self._loaded:
            self.load()
        self._data[key] = value
        self.save()

    def get_all(self) -> dict:
        """获取所有配置"""
        if not self._loaded:
            self.load()
        return dict(self._data)

    def reset(self):
        """重置为默认配置"""
        self._data = dict(DEFAULT_CONFIG)
        self.save()

    def reset_key(self, key: str):
        """重置单个配置项"""
        if key in DEFAULT_CONFIG:
            self._data[key] = DEFAULT_CONFIG[key]
            self.save()

    # ─── 布局持久化 ─────────────────────────────────────

    def save_app_layout(self, layout: dict):
        """保存应用排列布局 {app_id: {"page": int, "index": int}}"""
        self.set("app_layout", layout)

    def get_app_layout(self) -> dict:
        """获取应用排列布局"""
        return self.get("app_layout", {})

    def add_hidden_app(self, app_id: str):
        """隐藏一个应用"""
        hidden = self.get("hidden_apps", [])
        if app_id not in hidden:
            hidden.append(app_id)
            self.set("hidden_apps", hidden)

    def remove_hidden_app(self, app_id: str):
        """取消隐藏"""
        hidden = self.get("hidden_apps", [])
        if app_id in hidden:
            hidden.remove(app_id)
            self.set("hidden_apps", hidden)

    # ─── 开机自启动 ─────────────────────────────────────

    def set_auto_start(self, enabled: bool):
        """设置开机自启动"""
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "MacLaunchpad"

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                                 winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
            if enabled:
                exe_path = sys.executable
                script_path = str(Path(__file__).parent.parent / "main.py")
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ,
                                  f'"{exe_path}" "{script_path}"')
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
            self.set("auto_start", enabled)
        except OSError as e:
            print(f"[Config] 设置自启动失败: {e}")
