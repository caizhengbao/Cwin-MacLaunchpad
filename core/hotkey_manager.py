# -*- coding: utf-8 -*-
"""
全局快捷键管理模块
使用 Win32 RegisterHotKey API 注册系统级全局快捷键。
"""

import ctypes
import ctypes.wintypes as wintypes
import threading
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal

# 修饰键常量
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

# 虚拟键码映射
VK_MAP = {
    "space": 0x20, "enter": 0x0D, "tab": 0x09, "escape": 0x1B,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "backspace": 0x08, "delete": 0x2E, "insert": 0x2D,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD,
    "\\": 0xDC, ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
}

# 字母和数字
for c in "abcdefghijklmnopqrstuvwxyz":
    VK_MAP[c] = ord(c.upper())
for c in "0123456789":
    VK_MAP[c] = ord(c)


def parse_hotkey_string(hotkey_str: str):
    """
    解析快捷键字符串，如 'ctrl+space', 'alt+shift+f12'
    返回 (modifiers, vk_code)
    """
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    modifiers = 0
    vk_code = 0

    for part in parts:
        if part in ("ctrl", "control"):
            modifiers |= MOD_CONTROL
        elif part in ("alt",):
            modifiers |= MOD_ALT
        elif part in ("shift",):
            modifiers |= MOD_SHIFT
        elif part in ("win", "super", "meta"):
            modifiers |= MOD_WIN
        elif part in VK_MAP:
            vk_code = VK_MAP[part]
        else:
            print(f"[HotkeyManager] 未知键: {part}")

    return modifiers | MOD_NOREPEAT, vk_code


class HotkeyManager(QObject):
    """全局快捷键管理器"""

    hotkey_triggered = pyqtSignal()

    HOTKEY_ID = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._registered = False
        self._hotkey_str = ""

    def register(self, hotkey_str: str):
        """注册全局快捷键"""
        self.unregister()  # 先注销已有的

        self._hotkey_str = hotkey_str
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def unregister(self):
        """注销全局快捷键"""
        self._running = False
        if self._thread and self._thread.is_alive():
            # 发送 WM_QUIT 终止消息循环
            if self._thread.ident:
                ctypes.windll.user32.PostThreadMessageW(
                    self._thread.ident, 0x0012, 0, 0  # WM_QUIT
                )
            self._thread.join(timeout=2)
        self._thread = None
        self._registered = False

    def _listen_loop(self):
        """在独立线程中监听全局快捷键"""
        modifiers, vk_code = parse_hotkey_string(self._hotkey_str)

        if vk_code == 0:
            print(f"[HotkeyManager] 无效的快捷键: {self._hotkey_str}")
            return

        # 注册快捷键（必须在同一线程）
        result = ctypes.windll.user32.RegisterHotKey(
            None, self.HOTKEY_ID, modifiers, vk_code
        )

        if not result:
            print(f"[HotkeyManager] 注册快捷键失败: {self._hotkey_str} (可能已被占用)")
            return

        self._registered = True
        print(f"[HotkeyManager] 已注册快捷键: {self._hotkey_str}")

        # 消息循环
        msg = wintypes.MSG()
        while self._running:
            result = ctypes.windll.user32.GetMessageW(
                ctypes.byref(msg), None, 0, 0
            )
            if result <= 0:
                break
            if msg.message == 0x0312:  # WM_HOTKEY
                if msg.wParam == self.HOTKEY_ID:
                    self.hotkey_triggered.emit()

        # 注销
        ctypes.windll.user32.UnregisterHotKey(None, self.HOTKEY_ID)
        self._registered = False
        print(f"[HotkeyManager] 已注销快捷键: {self._hotkey_str}")

    def update_hotkey(self, new_hotkey_str: str):
        """更新快捷键"""
        if new_hotkey_str != self._hotkey_str:
            self.register(new_hotkey_str)
