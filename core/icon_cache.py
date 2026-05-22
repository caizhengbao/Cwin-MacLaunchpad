# -*- coding: utf-8 -*-
"""
图标缓存模块
将提取的图标缓存到磁盘，避免每次启动都重新提取。
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict

from PyQt5.QtGui import QPixmap

from .config import get_cache_dir
from .icon_extractor import IconExtractor
from .app_scanner import AppInfo


class IconCache:
    """图标缓存管理器"""

    def __init__(self, icon_size: int = 256):
        self.cache_dir = get_cache_dir()
        self.icon_size = icon_size
        self.extractor = IconExtractor(target_size=icon_size)
        self._memory_cache: Dict[str, QPixmap] = {}
        self._meta_path = self.cache_dir / "cache_meta.json"
        self._meta = self._load_meta()

    def _load_meta(self) -> dict:
        """加载缓存元数据"""
        if self._meta_path.exists():
            try:
                with open(self._meta_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _save_meta(self):
        """保存缓存元数据"""
        try:
            with open(self._meta_path, "w", encoding="utf-8") as f:
                json.dump(self._meta, f)
        except IOError:
            pass

    def _cache_key(self, app: AppInfo) -> str:
        """生成缓存键"""
        return app.app_id

    def _cache_file(self, key: str) -> Path:
        """缓存文件路径"""
        return self.cache_dir / f"{key}.png"

    def get_icon(self, app: AppInfo) -> Optional[QPixmap]:
        """获取应用图标（优先内存 → 磁盘 → 提取）"""
        key = self._cache_key(app)

        # 1. 内存缓存
        if key in self._memory_cache:
            return self._memory_cache[key]

        # 2. 磁盘缓存
        cache_file = self._cache_file(key)
        if cache_file.exists() and self._is_cache_valid(app, key):
            pixmap = QPixmap(str(cache_file))
            if not pixmap.isNull():
                self._memory_cache[key] = pixmap
                return pixmap

        # 3. 提取
        pixmap = self.extractor.extract(app.target_path, app.icon_location)
        if pixmap and not pixmap.isNull():
            # 保存到磁盘缓存
            pixmap.save(str(cache_file), "PNG")
            # 更新元数据
            mtime = ""
            if os.path.exists(app.target_path):
                mtime = str(os.path.getmtime(app.target_path))
            self._meta[key] = {
                "target": app.target_path,
                "mtime": mtime,
            }
            self._save_meta()
            # 保存到内存缓存
            self._memory_cache[key] = pixmap
            return pixmap

        return None

    def _is_cache_valid(self, app: AppInfo, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self._meta:
            return False
        meta = self._meta[key]
        # 检查目标文件是否改变
        if os.path.exists(app.target_path):
            current_mtime = str(os.path.getmtime(app.target_path))
            if meta.get("mtime") != current_mtime:
                return False
        return True

    def clear_memory_cache(self):
        """释放内存缓存（用于内存压缩）"""
        self._memory_cache.clear()

    def clear_all(self):
        """清除所有缓存"""
        self._memory_cache.clear()
        for f in self.cache_dir.glob("*.png"):
            try:
                f.unlink()
            except OSError:
                pass
        self._meta = {}
        self._save_meta()

    def preload_icons(self, apps: list):
        """预加载所有应用图标"""
        for app in apps:
            self.get_icon(app)
