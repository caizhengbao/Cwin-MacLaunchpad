# -*- coding: utf-8 -*-
"""
应用库模块 (纯手工模式)
负责管理用户手动添加的应用数据，保存到本地 JSON。
"""

import os
import json
import hashlib
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Optional


@dataclass
class AppInfo:
    """应用信息数据类"""
    name: str                          # 显示名称
    target_path: str                   # 目标 exe 路径
    working_dir: str = ""              # 工作目录
    icon_location: str = ""            # 图标位置 (path,index)
    shortcut_path: str = ""            # 快捷方式 .lnk 路径
    source: str = "custom"             # 来源 (默认 custom)
    app_id: str = ""                   # 唯一标识 (MD5 of target_path, or random for folders)
    arguments: str = ""                # 启动参数
    grid_index: int = -1               # 网格固定坐标 (-1代表未分配)
    is_folder: bool = False            # 是否为文件夹
    children_ids: List[str] = field(default_factory=list) # 文件夹内的子应用 ID 列表

    def __post_init__(self):
        if not self.app_id and self.target_path:
            raw = self.target_path.lower().strip()
            self.app_id = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        elif not self.app_id and self.is_folder:
            import uuid
            self.app_id = f"folder_{uuid.uuid4().hex[:8]}"

    @classmethod
    def from_dict(cls, d: dict):
        return cls(**d)


class AppScanner:
    """本地应用库管理器 (取代原有的全盘扫描)"""

    def __init__(self):
        self._shell = None
        # 数据存放目录
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        self.db_path = self.data_dir / "apps_db.json"
        
        # 内存缓存
        self.apps: List[AppInfo] = []
        self.load_db()

    def _get_shell(self):
        """懒加载 WScript.Shell COM 对象"""
        if self._shell is None:
            try:
                import win32com.client
                self._shell = win32com.client.Dispatch("WScript.Shell")
            except Exception as e:
                print(f"[AppManager] 无法创建 WScript.Shell: {e}")
        return self._shell

    def load_db(self):
        """从 JSON 加载应用库"""
        self.apps = []
        needs_save = False
        if self.db_path.exists():
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        self.apps.append(AppInfo.from_dict(item))
            except Exception as e:
                print(f"[AppManager] 加载数据库失败: {e}")
                
        # 找出所有在文件夹里的子应用 ID
        all_children = set()
        for a in self.apps:
            if a.is_folder:
                all_children.update(cid for cid in a.children_ids if cid)
                
        # 修复之前因为各种 bug 导致子应用拥有 >=0 的 grid_index
        for app in self.apps:
            if app.app_id in all_children and app.grid_index >= 0:
                app.grid_index = -1
                needs_save = True
                
        # 为真正在外部但没有 grid_index 的旧版本数据分配 grid_index
        used_indices = {a.grid_index for a in self.apps if a.grid_index >= 0}
        new_index = 0
        for app in self.apps:
            if app.grid_index < 0 and app.app_id not in all_children:
                while new_index in used_indices:
                    new_index += 1
                app.grid_index = new_index
                used_indices.add(new_index)
                needs_save = True
                
        if needs_save:
            self.save_db()

    def _compact_grid_indices(self):
        """已禁用：用户希望像 Windows 桌面一样可以自由留空排布，而不是强制吸附连续"""
        pass

    def clean_folders(self):
        """清理空文件夹或只剩一个应用的文件夹，确保解散和回收"""
        folders_to_delete = []
        for app in list(self.apps):
            if getattr(app, "is_folder", False):
                # 保留空字符串 "" 作为位置占位符，只过滤已删除的具体子应用
                app.children_ids = [cid if (not cid or self._get_app(cid) is not None) else "" for cid in app.children_ids]
                
                # 检查实际有效的应用个数
                active_ids = [cid for cid in app.children_ids if cid]
                if len(active_ids) == 0:
                    folders_to_delete.append(app)
                elif len(active_ids) == 1:
                    # 只剩下一个应用，解散该文件夹
                    remaining_id = active_ids[0]
                    remaining_app = self._get_app(remaining_id)
                    if remaining_app:
                        remaining_app.grid_index = app.grid_index
                    folders_to_delete.append(app)
        
        if folders_to_delete:
            self.apps = [a for a in self.apps if a not in folders_to_delete]

    def save_db(self):
        """保存应用库到 JSON"""
        try:
            self.clean_folders()
            with open(self.db_path, "w", encoding="utf-8") as f:
                data = [asdict(app) for app in self.apps]
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[AppManager] 保存数据库失败: {e}")

    def scan_all(self) -> List[AppInfo]:
        """向后兼容：返回所有保存的应用"""
        return self.apps

    def add_from_file(self, file_path: str) -> Optional[AppInfo]:
        """将外部文件 (.lnk 或 .exe) 加入到库中"""
        path = Path(file_path)
        if not path.exists():
            return None

        app = None
        if path.suffix.lower() == ".lnk":
            app = self._parse_shortcut(path)
        elif path.suffix.lower() == ".exe":
            app = AppInfo(
                name=path.stem,
                target_path=str(path),
                working_dir=str(path.parent)
            )

        if app:
            if existing := self._get_app(app.app_id):
                return existing
            
            used = {a.grid_index for a in self.apps if a.grid_index >= 0}
            app.grid_index = next(i for i in range(len(self.apps) + 1) if i not in used)
            self.apps.append(app)
            self.save_db()
            return app
        return None

    def _get_app(self, app_id: str) -> Optional['AppInfo']:
        return next((a for a in self.apps if a.app_id == app_id), None)

    def update_app_details(self, app_id: str, new_name: str = None, new_grid_index: int = None):
        """更新应用属性并保存"""
        app = self._get_app(app_id)
        if not app:
            return False
            
        if new_name is not None:
            app.name = new_name
        if new_grid_index is not None:
            if conflict := next((a for a in self.apps if a != app and a.grid_index == new_grid_index), None):
                if app.grid_index >= 0:
                    conflict.grid_index = app.grid_index
                else:
                    used = {a.grid_index for a in self.apps if a.grid_index >= 0}
                    conflict.grid_index = next(i for i in range(len(self.apps) + 2) if i not in used)
            app.grid_index = new_grid_index
            
            # 如果应用被放置到了主网格上，说明它被移出了文件夹
            if new_grid_index >= 0:
                for f in self.apps:
                    if getattr(f, "is_folder", False) and app_id in f.children_ids:
                        idx = f.children_ids.index(app_id)
                        f.children_ids[idx] = ""
                        
        self.save_db()
        return True

    def remove_app(self, app_id: str):
        """移除应用或文件夹"""
        self.apps = [app for app in self.apps if app.app_id != app_id]
        # 如果是移除某个子应用，从所有文件夹的 children_ids 中清理并以空字符占位
        for app in self.apps:
            if app.is_folder and app_id in app.children_ids:
                idx = app.children_ids.index(app_id)
                app.children_ids[idx] = ""
        self.save_db()

    def create_folder(self, folder_name: str, app_id_1: str, app_id_2: str) -> Optional['AppInfo']:
        """将两个应用合并为一个新文件夹"""
        app1, app2 = self._get_app(app_id_1), self._get_app(app_id_2)
        if not app1 or not app2:
            return None
            
        folder = AppInfo(
            name=folder_name,
            target_path="",
            is_folder=True,
            children_ids=[app_id_1, app_id_2],
            grid_index=app1.grid_index
        )
        
        # 将被收纳的应用的 grid_index 设置为 -1（不显示在主网格）
        app1.grid_index = -1
        app2.grid_index = -1
        
        for f in self.apps:
            if getattr(f, "is_folder", False):
                if app_id_1 in f.children_ids:
                    idx = f.children_ids.index(app_id_1)
                    f.children_ids[idx] = ""
                if app_id_2 in f.children_ids:
                    idx = f.children_ids.index(app_id_2)
                    f.children_ids[idx] = ""
        
        self.apps.append(folder)
        self.save_db()
        return folder

    def add_to_folder(self, folder_id: str, app_id: str):
        """将应用加入现有文件夹"""
        folder, app = self._get_app(folder_id), self._get_app(app_id)
        if folder and app and getattr(folder, "is_folder", False):
            if app_id not in folder.children_ids:
                try:
                    empty_idx = folder.children_ids.index("")
                    folder.children_ids[empty_idx] = app_id
                except ValueError:
                    folder.children_ids.append(app_id)
            app.grid_index = -1
            
            # 清理：确保应用只存在于当前文件夹中
            for f in self.apps:
                if getattr(f, "is_folder", False) and f.app_id != folder_id and app_id in f.children_ids:
                    idx = f.children_ids.index(app_id)
                    f.children_ids[idx] = ""
                    
            self._compact_grid_indices()
            self.save_db()

    def remove_from_folder(self, folder_id: str, app_id: str, new_grid_index: int = -1):
        """将应用从文件夹移出到主网格"""
        folder, app = self._get_app(folder_id), self._get_app(app_id)
        if folder and app and folder.is_folder and app_id in folder.children_ids:
            idx = folder.children_ids.index(app_id)
            folder.children_ids[idx] = ""
            if new_grid_index >= 0:
                app.grid_index = new_grid_index
            else:
                used = {a.grid_index for a in self.apps if a.grid_index >= 0}
                app.grid_index = next(i for i in range(len(self.apps) + 1) if i not in used)
            self.save_db()

    def reorder_apps(self, new_order_ids: List[str]):
        """根据给定的 ID 列表重新排序"""
        app_map = {app.app_id: app for app in self.apps}
        self.apps = [app_map.pop(aid) for aid in new_order_ids if aid in app_map] + list(app_map.values())
        self.save_db()

    def _parse_shortcut(self, lnk_path: Path) -> Optional[AppInfo]:
        """解析 .lnk 快捷方式文件"""
        shell = self._get_shell()
        if shell is None:
            return None

        try:
            shortcut = shell.CreateShortCut(str(lnk_path))
            target = shortcut.TargetPath
            working_dir = shortcut.WorkingDirectory
            icon_loc = shortcut.IconLocation
            arguments = shortcut.Arguments

            # 从快捷方式文件名提取显示名称
            name = lnk_path.stem

            return AppInfo(
                name=name,
                target_path=target,
                working_dir=working_dir or "",
                icon_location=icon_loc or "",
                shortcut_path=str(lnk_path),
                source="custom",
                arguments=arguments or "",
            )
        except Exception as e:
            print(f"[AppManager] COM 解析错误 {lnk_path}: {e}")
            return None

    def launch_app(self, app: AppInfo):
        """启动应用"""
        import subprocess
        try:
            if app.shortcut_path and os.path.exists(app.shortcut_path):
                os.startfile(app.shortcut_path)
            elif app.target_path and os.path.exists(app.target_path):
                cwd = app.working_dir if app.working_dir and os.path.isdir(
                    app.working_dir) else None
                subprocess.Popen(
                    [app.target_path] + (app.arguments.split() if app.arguments else []),
                    cwd=cwd,
                    shell=False,
                )
            else:
                print(f"[AppManager] 无法启动: {app.name}")
        except Exception as e:
            print(f"[AppManager] 启动失败 {app.name}: {e}")
