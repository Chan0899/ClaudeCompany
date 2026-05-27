"""
状态持久化 - 服务器重启后恢复任务和对话历史

所有状态保存在 workspace/_state/ 目录下的 JSON 文件中
"""
import os
import json
import threading
from config import WORKSPACE_DIR


STATE_DIR = os.path.join(WORKSPACE_DIR, "_state")


class Persistence:
    """简易 JSON 文件持久化"""

    def __init__(self):
        os.makedirs(STATE_DIR, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, key: str) -> str:
        return os.path.join(STATE_DIR, f"{key}.json")

    def save(self, key: str, data):
        """保存数据到文件"""
        with self._lock:
            path = self._path(key)
            tmppath = path + ".tmp"
            try:
                with open(tmppath, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                os.replace(tmppath, path)
            except Exception as e:
                print(f"[Persistence] 保存 {key} 失败: {e}")

    def load(self, key: str, default=None):
        """从文件加载数据"""
        path = self._path(key)
        if not os.path.exists(path):
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Persistence] 加载 {key} 失败: {e}")
            return default

    def delete(self, key: str):
        """删除持久化数据"""
        path = self._path(key)
        try:
            os.remove(path)
        except OSError:
            pass


# 全局单例
persistence = Persistence()
