# -*- coding: utf-8 -*-
"""
动画系统模块
提供所有 macOS Launchpad 风格动画的工厂方法。
"""

from PyQt5.QtCore import (
    QPropertyAnimation, QParallelAnimationGroup, QEasingCurve, QPoint
)
from PyQt5.QtWidgets import QWidget


class AnimationManager:
    """动画管理器 - 管理所有 Launchpad 动画"""

    def __init__(self, config):
        self.config = config
        self._active_groups = []

    def _cleanup_group(self, group):
        if group in self._active_groups:
            self._active_groups.remove(group)

    # ─── 打开动画 ────────────────────────────────────────

    def create_open_animation(self, bg_widget, icon_widgets, search_widget=None):
        """
        创建完整的打开动画序列：
        1. 背景淡入
        2. 图标从小到大缩放（交错延迟）
        3. 搜索栏滑入
        """
        master_group = QParallelAnimationGroup()
        self._active_groups.append(master_group)
        master_group.finished.connect(lambda: self._cleanup_group(master_group))

        # 1. 背景淡入
        bg_widget.setWindowOpacity(0.0)

        bg_anim = QPropertyAnimation(bg_widget, b"windowOpacity")
        bg_anim.setDuration(self.config.get("anim_open_bg_duration", 300))
        bg_anim.setStartValue(0.0)
        bg_anim.setEndValue(1.0)
        bg_anim.setEasingCurve(QEasingCurve.OutCubic)
        master_group.addAnimation(bg_anim)

        # 2. 移除图标单独的 QGraphicsOpacityEffect 动画（解决 QPainter 冲突报错）
        # 让所有图标随 windowOpacity 一起淡入即可，极其流畅且无报错
        return master_group

    # ─── 关闭动画 ────────────────────────────────────────

    def create_close_animation(self, bg_widget, icon_widgets, search_widget=None):
        """
        创建完整的关闭动画序列：
        1. 图标缩小 + 淡出
        2. 背景淡出
        """
        master_group = QParallelAnimationGroup()
        self._active_groups.append(master_group)
        master_group.finished.connect(lambda: self._cleanup_group(master_group))

        duration = self.config.get("anim_close_bg_duration", 150)

        # 1. 移除单独图标的透明度效果，直接使用底层窗口整体淡出
        bg_anim = QPropertyAnimation(bg_widget, b"windowOpacity")
        bg_anim.setDuration(duration)
        bg_anim.setStartValue(1.0)
        bg_anim.setEndValue(0.0)
        bg_anim.setEasingCurve(QEasingCurve.InCubic)
        master_group.addAnimation(bg_anim)

        return master_group

    # ─── 页面切换动画 ────────────────────────────────────

    def create_page_switch_animation(self, container: QWidget, 
                                      direction: int, page_width: int):
        """
        创建页面切换动画。
        direction: -1=左滑(下一页), 1=右滑(上一页)
        """
        duration = self.config.get("anim_page_switch_duration", 400)
        
        current_pos = container.pos()
        target_x = current_pos.x() + (direction * page_width)

        anim = QPropertyAnimation(container, b"pos")
        anim.setDuration(duration)
        anim.setStartValue(current_pos)
        anim.setEndValue(QPoint(target_x, current_pos.y()))
        anim.setEasingCurve(QEasingCurve.InOutCubic)

        return anim

    # ─── 悬停动画 ────────────────────────────────────────

    @staticmethod
    def create_hover_enter_animation(widget: QWidget, duration: int = 150):
        """图标悬停放大动画"""
        effect = widget.graphicsEffect()
        if not effect:
            return None
        # 我们通过样式表的 transform 来处理悬停，这里只提供备用
        return None

    @staticmethod
    def create_hover_leave_animation(widget: QWidget, duration: int = 150):
        """图标悬停恢复动画"""
        return None

    def stop_all(self):
        """停止所有正在播放的动画"""
        for group in list(self._active_groups):
            group.stop()
        self._active_groups.clear()
