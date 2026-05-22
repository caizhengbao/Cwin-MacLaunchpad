# -*- coding: utf-8 -*-
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QGraphicsBlurEffect
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QPixmap, QPainter, QColor

def blur_pixmap_effect(pixmap, scale_factor=0.2, radius=18):
    if pixmap.isNull():
        return pixmap
    w, h = pixmap.width(), pixmap.height()
    sw, sh = max(1, int(w * scale_factor)), max(1, int(h * scale_factor))
    
    # 降采样
    small = pixmap.scaled(sw, sh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    
    # 使用 QGraphicsBlurEffect
    label = QLabel()
    label.setAttribute(Qt.WA_TranslucentBackground, True)
    label.setPixmap(small)
    label.resize(sw, sh)
    
    blur = QGraphicsBlurEffect(label)
    blur.setBlurRadius(radius)
    blur.setBlurHints(QGraphicsBlurEffect.QualityHint)
    label.setGraphicsEffect(blur)
    
    # 渲染
    blurred_small = label.grab()
    
    # 升采样
    return blurred_small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

def test():
    app = QApplication(sys.argv)
    
    # 创建一个测试用的 pixmap
    pixmap = QPixmap(800, 600)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setBrush(QColor(100, 150, 255))
    painter.drawRect(50, 50, 200, 200)
    painter.setBrush(QColor(255, 100, 100))
    painter.drawEllipse(300, 200, 300, 300)
    painter.end()
    
    # 执行模糊
    blurred = blur_pixmap_effect(pixmap)
    print("Original size:", pixmap.size())
    print("Blurred size:", blurred.size())
    print("Is null:", blurred.isNull())
    return 0

if __name__ == '__main__':
    test()
