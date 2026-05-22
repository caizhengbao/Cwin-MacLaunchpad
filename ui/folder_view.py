from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QGraphicsOpacityEffect, QLabel, QGraphicsBlurEffect
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal, pyqtProperty
from PyQt5.QtGui import QPainter, QColor, QPainterPath, QPen, QPixmap

from core.app_scanner import AppInfo
from ui.app_grid import AppGrid
from dataclasses import replace

class FolderView(QWidget):
    """文件夹展开视图"""
    
    # 信号
    closed = pyqtSignal()
    
    def __init__(self, parent_window, folder_app: AppInfo):
        super().__init__(parent_window)
        self.parent_window = parent_window
        self.folder_app = folder_app
        self.config = parent_window.config
        self.scanner = parent_window.scanner
        self.icon_cache = parent_window.icon_cache
        
        self.resize(parent_window.size())
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAcceptDrops(True)
        
        self.init_ui()
        
        # 定义动画
        self._anim_progress = 0.0
        self.anim = QPropertyAnimation(self, b"animProgress")
        self.anim.setDuration(250)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)

    def _blur_pixmap(self, pixmap, scale_factor=0.2, blur_radius=18):
        """
        利用 QGraphicsBlurEffect 对适度降采样的图像进行高质量模糊处理后还原，
        在不增加 CPU 耗时的前提下，完全打散色彩断层并消除斑块和方块锯齿感。
        """
        if pixmap.isNull():
            return pixmap
        w, h = pixmap.width(), pixmap.height()
        
        # 1. 适度降采样
        sw, sh = max(1, int(w * scale_factor)), max(1, int(h * scale_factor))
        small = pixmap.scaled(sw, sh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        
        # 2. 应用高质量 QGraphicsBlurEffect 模糊
        label = QLabel()
        label.setAttribute(Qt.WA_TranslucentBackground, True)
        label.setStyleSheet("background: transparent;")
        label.setPixmap(small)
        label.resize(sw, sh)
        
        blur = QGraphicsBlurEffect(label)
        blur.setBlurRadius(blur_radius)
        blur.setBlurHints(QGraphicsBlurEffect.QualityHint)
        label.setGraphicsEffect(blur)
        
        # 3. 抓取模糊后的 Pixmap 并放大到原始尺寸
        blurred_small = label.grab()
        return blurred_small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        
    def init_ui(self):
        # 整体布局 (居中对齐)
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignCenter)
        
        # 顶部标题输入框 (支持直接重命名)
        self.title_edit = QLineEdit(self.folder_app.name)
        self.title_edit.setAlignment(Qt.AlignCenter)
        self.title_edit.setFixedWidth(400)
        self.title_edit.setStyleSheet("""
            QLineEdit {
                color: white;
                background: transparent;
                border: none;
                font-size: 32px;
                font-weight: bold;
            }
            QLineEdit:focus {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 8px;
            }
        """)
        self.title_edit.editingFinished.connect(self._on_title_edited)
        self.layout.addWidget(self.title_edit, 0, Qt.AlignHCenter)
        
        self.layout.addSpacing(30)
        
        # 内部 AppGrid
        # 注意: 需要传入 anim_manager 和 scanner，并且设置 draw_background=False 避免出现两个重叠框
        self.grid = AppGrid(self.config, self.icon_cache, self.parent_window.anim_manager, self.scanner, self, draw_background=False)
        
        # 覆写网格的尺寸，适配文件夹展开视图 (比如 4x4)
        self.grid.cols = 4
        self.grid.rows = 4
        self.grid.spacing_h = 120
        self.grid.spacing_v = 130
        # 固定尺寸刚好放下 4 列
        self.grid.setFixedSize(self.grid.cols * self.grid.spacing_h, self.grid.rows * self.grid.spacing_v)
        self.layout.addWidget(self.grid, 0, Qt.AlignHCenter)
        
        # 加载内容
        self.load_folder_apps()
        
        # 统一绑定事件
        self.grid.icon_clicked.connect(self._on_app_clicked)
        self.grid.icon_delete_requested.connect(self._on_app_deleted)
        self.grid.icon_drag_started.connect(self._on_drag_started)
        self.grid.icon_drag_finished.connect(self._on_drag_finished)
            
    def _on_drag_started(self, app_info):
        pass
        
    def _on_drag_finished(self, app_info):
        pass

    def _safe_delete(self):
        self.close()
        self.deleteLater()
        
    def load_folder_apps(self):
        app_map = {a.app_id: a for a in self.scanner.apps}
        children = []
        for idx, cid in enumerate(self.folder_app.children_ids):
            a = app_map.get(cid)
            if a:
                # 浅拷贝以避免污染全局真实的 grid_index (-1)
                child_copy = replace(a, grid_index=idx)
                children.append(child_copy)
        self.grid.set_apps(children)
        
    def _on_title_edited(self):
        new_name = self.title_edit.text().strip()
        if new_name and new_name != self.folder_app.name:
            self.folder_app.name = new_name
            self.scanner.save_db()
            self.parent_window.load_apps() # 刷新外面文件夹的名字
            
    def _on_app_clicked(self, app_info):
        self.parent_window.hide_launchpad()
        self.scanner.launch_app(app_info)
        
    def _on_app_deleted(self, app_info):
        # 从文件夹里移除，并且移回主网格
        self.scanner.remove_from_folder(self.folder_app.app_id, app_info.app_id)
        if self.folder_app not in self.scanner.apps:
            # 文件夹已被解散，关闭当前视图并刷新主网格
            self.hide_view()
            self.parent_window.load_apps()
        else:
            self.load_folder_apps()
            self.parent_window.load_apps()

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("app_id:"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("app_id:"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        text = event.mimeData().text()
        if not text.startswith("app_id:"):
            event.ignore()
            return
            
        app_id = text.split(":")[1]
        pos = event.pos()
        
        # 计算包含内容的文件夹圆角板矩形
        box_width = self.grid.width() + 40
        box_height = self.grid.height() + 120
        box_x = (self.width() - box_width) // 2
        box_y = (self.height() - box_height) // 2
        
        from PyQt5.QtCore import QRect
        box_rect = QRect(box_x, box_y, box_width, box_height)
        
        if box_rect.contains(pos):
            # 在文件夹内部：重排并吸附（支持自由留空）
            if app_id in self.folder_app.children_ids:
                grid_pos = self.grid.mapFrom(self, pos)
                target_index = self.grid.get_index_at_pos(grid_pos)
                
                # 限制在 4x4 的 16 个格点内
                if 0 <= target_index < 16:
                    old_index = self.folder_app.children_ids.index(app_id)
                    if old_index != target_index:
                        # 确保列表长度补齐到目标索引
                        while len(self.folder_app.children_ids) <= target_index:
                            self.folder_app.children_ids.append("")
                        
                        target_app_id = self.folder_app.children_ids[target_index]
                        if target_app_id and target_app_id != app_id:
                            # 如果目标格有人，交换位置
                            self.folder_app.children_ids[old_index] = target_app_id
                            self.folder_app.children_ids[target_index] = app_id
                        else:
                            # 目标格为空，原位置设为空，新位置设为 app_id
                            self.folder_app.children_ids[old_index] = ""
                            self.folder_app.children_ids[target_index] = app_id
                        
                        # 移除尾部连续的空占位
                        while self.folder_app.children_ids and self.folder_app.children_ids[-1] == "":
                            self.folder_app.children_ids.pop()
                            
                        self.scanner.save_db()
                        self.load_folder_apps()
                        # 同时也刷新外面主网格中此文件夹的缩微九宫格图标
                        self.parent_window.load_apps()
            event.acceptProposedAction()
        else:
            # 在文件夹外部：移出文件夹并放入主网格相应位置
            main_window = self.parent_window
            main_pos = self.mapTo(main_window, pos)
            grid_pos_main = main_window.app_grid.mapFrom(main_window, main_pos)
            target_grid_index = main_window.app_grid.get_index_at_pos(grid_pos_main)
            
            # 先将其从文件夹移出（默认放到一个可用的空网格位置上）
            self.scanner.remove_from_folder(self.folder_app.app_id, app_id, new_grid_index=-1)
            # 如果释放位置在主网格内，则将其重新移位至目标位置，利用 update_app_details 中的冲突处理逻辑
            if target_grid_index >= 0:
                self.scanner.update_app_details(app_id, new_grid_index=target_grid_index)
            
            # 关闭文件夹并加载主窗口
            self.hide_view()
            main_window.load_apps()
            event.acceptProposedAction()
        
    def mousePressEvent(self, event):
        # 去除当前子控件的焦点
        self.setFocus()
        
        # 点击空白处关闭
        child = self.childAt(event.pos())
        if child is None or child is self:
            self.hide_view()
            
    def show_view(self):
        # 抓取当前窗口在文件夹展开之前的画面快照并执行快速磨砂模糊缓存
        if self.parent_window:
            try:
                screenshot = self.parent_window.grab()
                self._bg_blur_pixmap = self._blur_pixmap(screenshot, scale_factor=0.2, blur_radius=18)
            except Exception as e:
                print(f"[FolderView] 抓取并模糊底图快照失败: {e}")
                self._bg_blur_pixmap = None
        else:
            self._bg_blur_pixmap = None

        # 动态挂载不透明度效果，让子控件一同参与淡入动画
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)
        
        self.show()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        
        def on_show_finished():
            # 动画结束立刻卸载，恢复日常零负担渲染
            self.setGraphicsEffect(None)
            if hasattr(self, 'opacity_effect'):
                del self.opacity_effect
            try:
                self.anim.finished.disconnect()
            except TypeError:
                pass
                
        try:
            self.anim.finished.disconnect()
        except TypeError:
            pass
            
        self.anim.finished.connect(on_show_finished)
        self.anim.start()
        
    def hide_view(self):
        # 动态挂载不透明度效果，让子控件一同参与淡出动画
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(1.0)
        
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        
        def on_hide_finished():
            self.close()
            self.deleteLater()
            
        try:
            self.anim.finished.disconnect()
        except TypeError:
            pass
            
        self.anim.finished.connect(on_hide_finished)
        self.anim.start()
        self.closed.emit()

    # Qt 必须定义一个 pyqtProperty 才能给动画使用
    def getAnimProgress(self):
        return getattr(self, "_anim_progress", 0.0)
        
    def setAnimProgress(self, progress):
        self._anim_progress = progress
        self._opacity = progress
        if hasattr(self, "opacity_effect") and self.opacity_effect is not None:
            self.opacity_effect.setOpacity(progress)
        self.update()
        
    animProgress = pyqtProperty(float, fget=getAnimProgress, fset=setAnimProgress)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 1. 绘制全屏渐变黑色压暗遮罩，随动画进度渐变（加深以绝缘外层图标）
        overlay_color = QColor(0, 0, 0, int(180 * self._opacity))
        painter.fillRect(self.rect(), overlay_color)
        
        # 2. 计算包含内容的文件夹圆角板矩形
        box_width = self.grid.width() + 40
        box_height = self.grid.height() + 120
        box_x = (self.width() - box_width) // 2
        box_y = (self.height() - box_height) // 2
        
        path = QPainterPath()
        radius = 42 # 更大更平滑的圆角
        path.addRoundedRect(box_x, box_y, box_width, box_height, radius, radius)
        
        # 3. 绘制只在白色卡片内部展现的模糊背景（Frosted Glass）
        if hasattr(self, "_bg_blur_pixmap") and self._bg_blur_pixmap is not None and not self._bg_blur_pixmap.isNull():
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setClipPath(path)
            painter.setOpacity(self._opacity)
            painter.drawPixmap(0, 0, self._bg_blur_pixmap)
            painter.restore()
        
        # 4. 填充文件夹底板：半透明亮白色，叠在模糊背景之上形成白色磨砂质感 (从配置动态获取不透明度亮度)
        painter.save()
        painter.setOpacity(self._opacity)
        panel_opacity = self.config.get("folder_bg_opacity", 40)
        panel_color = QColor(255, 255, 255, panel_opacity)
        painter.fillPath(path, panel_color)
        painter.restore()
        
        # 4. 绘制细腻的半透明微光边框，强化悬浮立体感
        border_pen = QPen(QColor(255, 255, 255, int(30 * self._opacity)))
        border_pen.setWidth(1)
        painter.setPen(border_pen)
        painter.drawPath(path)
        
        painter.end()
