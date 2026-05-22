# -*- coding: utf-8 -*-
"""
毛玻璃效果模块
使用 Windows API 实现真正的原生动态高斯模糊 (DWM System Backdrop / Acrylic)。
彻底移除截屏假模糊，确保在有动态视频作为背景时也能实时透视。
"""

import ctypes
from ctypes import Structure, c_int, POINTER, byref, sizeof

# ─── Windows API 结构体 ─────────────────────────────────

class ACCENT_POLICY(Structure):
    _fields_ = [
        ("AccentState", c_int),
        ("AccentFlags", c_int),
        ("GradientColor", c_int),
        ("AnimationId", c_int),
    ]

class WINDOWCOMPOSITIONATTRIBDATA(Structure):
    _fields_ = [
        ("Attribute", c_int),
        ("Data", POINTER(ACCENT_POLICY)),
        ("SizeOfData", c_int),
    ]

# AccentState
ACCENT_ENABLE_BLURBEHIND = 3
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4

# DWM 常量
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMSBT_TRANSIENTWINDOW = 3  # Acrylic

def apply_blur_to_window(window) -> bool:
    """
    对窗口应用原生毛玻璃效果。优先尝试 Win11 System Backdrop，降级到 Win10 Acrylic/BlurBehind。
    并使用偏白、高透明度的着色。
    """
    if hasattr(window, '_bg_pixmap'):
        window._bg_pixmap = None  # 彻底清理旧的截图背景逻辑

    hwnd = int(window.winId())
    
    try:
        # 统一使用最基础的 BlurBehind (Aero Blur)，无杂色无 Acrylic 黑屏/白屏问题，透明度极高
        accent = ACCENT_POLICY()
        accent.AccentState = ACCENT_ENABLE_BLURBEHIND
        accent.AccentFlags = 0
        accent.GradientColor = 0

        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = 19  # WCA_ACCENT_POLICY
        data.Data = ctypes.pointer(accent)
        data.SizeOfData = sizeof(accent)

        user32 = ctypes.windll.user32
        res = user32.SetWindowCompositionAttribute(hwnd, byref(data))
        return bool(res)
    except Exception as e:
        print(f"[BlurEffect] 启用系统级动态模糊失败: {e}")
        return False
