# -*- coding: utf-8 -*-
"""
图标提取模块
从 .exe / .lnk 文件中提取高分辨率应用图标，转换为 QPixmap。
"""

import ctypes
import ctypes.wintypes as wintypes
import os
from typing import Optional

from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QFileIconProvider


# ─── Win32 常量 & 结构体 ──────────────────────────────────

SHGFI_ICON = 0x000000100
SHGFI_LARGEICON = 0x000000000
SHGFI_SMALLICON = 0x000000001
SHGFI_SYSICONINDEX = 0x000004000
SHGFI_USEFILEATTRIBUTES = 0x000000010

FILE_ATTRIBUTE_NORMAL = 0x80

# SHGetFileInfoW 结构体
class SHFILEINFO(ctypes.Structure):
    _fields_ = [
        ("hIcon", wintypes.HANDLE),
        ("iIcon", ctypes.c_int),
        ("dwAttributes", wintypes.DWORD),
        ("szDisplayName", ctypes.c_wchar * 260),
        ("szTypeName", ctypes.c_wchar * 80),
    ]


def _destroy_icon(hicon):
    """释放图标句柄"""
    if hicon:
        ctypes.windll.user32.DestroyIcon(hicon)


class IconExtractor:
    """从可执行文件中提取图标"""

    def __init__(self, target_size: int = 256):
        self.target_size = target_size
        self._file_icon_provider = QFileIconProvider()

    def extract(self, exe_path: str, icon_location: str = "") -> Optional[QPixmap]:
        """按优先级尝试多种提取方法"""
        methods = []
        if icon_location:
            methods.append(lambda: self._extract_from_icon_location(icon_location))
        if exe_path and os.path.exists(exe_path):
            methods.extend([
                lambda: self._extract_high_res(exe_path),
                lambda: self._extract_shgetfileinfo(exe_path),
                lambda: self._extract_qt_fallback(exe_path)
            ])
            
        for method in methods:
            pixmap = method()
            if pixmap and not pixmap.isNull():
                return self._scale_pixmap(pixmap)
        return None

    def _extract_from_icon_location(self, icon_location: str) -> Optional[QPixmap]:
        """从 icon_location 字符串提取图标 (格式: 'path,index')"""
        try:
            parts = icon_location.rsplit(",", 1)
            icon_path = parts[0].strip()
            icon_index = int(parts[1].strip()) if len(parts) > 1 else 0

            if not icon_path or not os.path.exists(icon_path):
                return None

            return self._extract_high_res(icon_path, icon_index)
        except (ValueError, IndexError):
            return None

    def _extract_high_res(self, file_path: str, index: int = 0) -> Optional[QPixmap]:
        """
        使用 PrivateExtractIcons 提取高分辨率图标 (256x256)。
        这是获取高分辨率图标最可靠的方法。
        """
        try:
            # PrivateExtractIcons 支持提取任意大小的图标
            PrivateExtractIcons = ctypes.windll.user32.PrivateExtractIconsW
            PrivateExtractIcons.argtypes = [
                wintypes.LPCWSTR,  # lpszFile
                ctypes.c_int,      # nIconIndex
                ctypes.c_int,      # cxIcon
                ctypes.c_int,      # cyIcon
                ctypes.POINTER(wintypes.HANDLE),  # phicon
                ctypes.POINTER(wintypes.UINT),     # piconid
                wintypes.UINT,     # nIcons
                wintypes.UINT,     # flags
            ]
            PrivateExtractIcons.restype = wintypes.UINT

            # 尝试从大到小提取
            for size in [256, 128, 64, 48, 32]:
                hicon = wintypes.HANDLE()
                icon_id = wintypes.UINT()

                result = PrivateExtractIcons(
                    file_path, index, size, size,
                    ctypes.byref(hicon), ctypes.byref(icon_id),
                    1, 0
                )

                if result > 0 and hicon.value:
                    pixmap = self._hicon_to_pixmap(hicon.value, size)
                    _destroy_icon(hicon.value)
                    if pixmap and not pixmap.isNull():
                        return pixmap

            return None
        except Exception as e:
            print(f"[IconExtractor] PrivateExtractIcons 失败: {e}")
            return None

    def _extract_shgetfileinfo(self, file_path: str) -> Optional[QPixmap]:
        """使用 SHGetFileInfo 提取图标（通常只有 32x32）"""
        try:
            info = SHFILEINFO()
            result = ctypes.windll.shell32.SHGetFileInfoW(
                file_path, 0, ctypes.byref(info), ctypes.sizeof(info),
                SHGFI_ICON | SHGFI_LARGEICON
            )

            if result and info.hIcon:
                pixmap = self._hicon_to_pixmap(info.hIcon, 32)
                _destroy_icon(info.hIcon)
                return pixmap

            return None
        except Exception as e:
            print(f"[IconExtractor] SHGetFileInfo 失败: {e}")
            return None

    def _extract_qt_fallback(self, file_path: str) -> Optional[QPixmap]:
        """使用 Qt 的 QFileIconProvider 作为兜底"""
        try:
            from PyQt5.QtCore import QFileInfo
            file_info = QFileInfo(file_path)
            icon = self._file_icon_provider.icon(file_info)
            if not icon.isNull():
                # 尝试获取最大尺寸
                sizes = icon.availableSizes()
                if sizes:
                    best = max(sizes, key=lambda s: s.width() * s.height())
                    return icon.pixmap(best)
                return icon.pixmap(QSize(48, 48))
        except Exception as e:
            print(f"[IconExtractor] 获取可执行文件图标失败: {e}")
        return None

    def _hicon_to_pixmap(self, hicon, size: int) -> Optional[QPixmap]:
        """将 HICON 转换为 QPixmap"""
        try:
            import win32gui
            import win32ui

            # 创建设备上下文
            hdc = win32gui.GetDC(0)
            hdc_mem = win32gui.CreateCompatibleDC(hdc)

            # 创建位图
            bmp = win32ui.CreateBitmap()
            bmp.CreateCompatibleBitmap(win32ui.CreateDCFromHandle(hdc), size, size)
            hdc_mem_obj = win32ui.CreateDCFromHandle(hdc_mem)
            hdc_mem_obj.SelectObject(bmp)

            # 填充透明背景
            brush = win32gui.CreateSolidBrush(0)
            win32gui.FillRect(hdc_mem, (0, 0, size, size), brush)
            win32gui.DeleteObject(brush)

            # 绘制图标
            win32gui.DrawIconEx(
                hdc_mem, 0, 0, hicon, size, size,
                0, 0, 0x0003  # DI_NORMAL
            )

            # 获取位图数据
            bmp_info = bmp.GetInfo()
            bmp_bits = bmp.GetBitmapBits(True)

            # 创建 QImage
            img = QImage(bmp_bits, bmp_info["bmWidth"], bmp_info["bmHeight"],
                         QImage.Format_ARGB32_Premultiplied)
            img = img.copy()  # 深拷贝，因为 bmp_bits 会被释放

            # 清理
            win32gui.DeleteDC(hdc_mem)
            win32gui.ReleaseDC(0, hdc)
            try:
                win32gui.DeleteObject(bmp.GetHandle())
            except Exception as e:
                print(f"[IconExtractor] 清理位图句柄失败: {e}")

            if img.isNull():
                return None

            return QPixmap.fromImage(img)

        except ImportError:
            # 如果 pywin32 不可用，使用 ctypes 方法
            return self._hicon_to_pixmap_ctypes(hicon, size)
        except Exception as e:
            print(f"[IconExtractor] hicon 转换失败: {e}")
            return None

    def _hicon_to_pixmap_ctypes(self, hicon, size: int) -> Optional[QPixmap]:
        """纯 ctypes 方式将 HICON 转为 QPixmap"""
        try:
            # 使用 GetIconInfo 获取位图
            class ICONINFO(ctypes.Structure):
                _fields_ = [
                    ("fIcon", wintypes.BOOL),
                    ("xHotspot", wintypes.DWORD),
                    ("yHotspot", wintypes.DWORD),
                    ("hbmMask", wintypes.HBITMAP),
                    ("hbmColor", wintypes.HBITMAP),
                ]

            info = ICONINFO()
            if not ctypes.windll.user32.GetIconInfo(hicon, ctypes.byref(info)):
                return None

            class BITMAP(ctypes.Structure):
                _fields_ = [
                    ("bmType", wintypes.LONG),
                    ("bmWidth", wintypes.LONG),
                    ("bmHeight", wintypes.LONG),
                    ("bmWidthBytes", wintypes.LONG),
                    ("bmPlanes", wintypes.WORD),
                    ("bmBitsPixel", wintypes.WORD),
                    ("bmBits", ctypes.c_void_p),
                ]

            bmp = BITMAP()
            if info.hbmColor:
                ctypes.windll.gdi32.GetObjectW(
                    info.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bmp)
                )
                width = bmp.bmWidth
                height = bmp.bmHeight

                # 创建 DIB
                class BITMAPINFOHEADER(ctypes.Structure):
                    _fields_ = [
                        ("biSize", wintypes.DWORD),
                        ("biWidth", wintypes.LONG),
                        ("biHeight", wintypes.LONG),
                        ("biPlanes", wintypes.WORD),
                        ("biBitCount", wintypes.WORD),
                        ("biCompression", wintypes.DWORD),
                        ("biSizeImage", wintypes.DWORD),
                        ("biXPelsPerMeter", wintypes.LONG),
                        ("biYPelsPerMeter", wintypes.LONG),
                        ("biClrUsed", wintypes.DWORD),
                        ("biClrImportant", wintypes.DWORD),
                    ]

                bmi = BITMAPINFOHEADER()
                bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
                bmi.biWidth = width
                bmi.biHeight = -height  # 自顶向下
                bmi.biPlanes = 1
                bmi.biBitCount = 32
                bmi.biCompression = 0

                buf_size = width * height * 4
                buf = ctypes.create_string_buffer(buf_size)

                hdc = ctypes.windll.user32.GetDC(0)
                ctypes.windll.gdi32.GetDIBits(
                    hdc, info.hbmColor, 0, height,
                    buf, ctypes.byref(bmi), 0
                )
                ctypes.windll.user32.ReleaseDC(0, hdc)

                img = QImage(buf, width, height, QImage.Format_ARGB32_Premultiplied)
                img = img.copy()

                # 清理位图
                ctypes.windll.gdi32.DeleteObject(info.hbmColor)
                if info.hbmMask:
                    ctypes.windll.gdi32.DeleteObject(info.hbmMask)

                return QPixmap.fromImage(img)

            # 清理
            if info.hbmColor:
                ctypes.windll.gdi32.DeleteObject(info.hbmColor)
            if info.hbmMask:
                ctypes.windll.gdi32.DeleteObject(info.hbmMask)

            return None

        except Exception as e:
            print(f"[IconExtractor] ctypes hicon 转换失败: {e}")
            return None

    def _scale_pixmap(self, pixmap: QPixmap) -> QPixmap:
        """将图标缩放到目标尺寸，保持高质量"""
        if pixmap.isNull():
            return pixmap
        if pixmap.width() == self.target_size and pixmap.height() == self.target_size:
            return pixmap
        return pixmap.scaled(
            self.target_size, self.target_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
