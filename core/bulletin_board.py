"""
公告板 - AI间通信协议 (跨进程安全)

每个AI可以在公告板上:
  1. 发布消息 (post) - 告知其他AI自己的设计决策
  2. 阅读消息 (read) - 了解其他AI的工作内容
  3. 检测冲突 (detect_conflicts) - 管理AI用于检查API不一致等

底层使用 workspace/_board/ 目录下的文件, 配合 FileLock 跨进程安全
"""
import os
import time
from config import WORKSPACE_DIR
from core.workspace import FileLock


BOARD_DIR = os.path.join(WORKSPACE_DIR, "_board")
BOARD_FILE = os.path.join(BOARD_DIR, "chat.md")


class Board:
    """跨进程公告板: AI通过读写 BOARD_FILE 进行协作"""

    def __init__(self):
        os.makedirs(BOARD_DIR, exist_ok=True)
        if not os.path.exists(BOARD_FILE):
            with open(BOARD_FILE, "w", encoding="utf-8") as f:
                f.write("# AI协作公告板\n\n> 所有AI在此留言, 协调工作\n\n---\n\n")

    def post(self, role: str, role_name: str, message: str):
        """
        AI发布消息到公告板 (跨进程安全)
        格式: ## [角色名] @ HH:MM:SS\n消息内容\n
        """
        timestamp = time.strftime("%H:%M:%S")
        entry = f"\n## [{role_name}] @ {timestamp}\n\n{message}\n\n---\n"

        with FileLock(BOARD_FILE):
            with open(BOARD_FILE, "a", encoding="utf-8") as f:
                f.write(entry)

        return entry

    def read(self) -> str:
        """读取公告板全部内容"""
        if not os.path.exists(BOARD_FILE):
            return ""
        with open(BOARD_FILE, "r", encoding="utf-8") as f:
            return f.read()

    def read_recent(self, since_minutes: int = 30) -> str:
        """读取最近的公告板消息 (摘要)"""
        content = self.read()
        lines = content.split("\n")
        # 返回整个内容, 调用方可自行截断
        if len(content) > 3000:
            return content[-3000:]  # 最近3000字符
        return content

    def detect_conflicts(self) -> list[dict]:
        """
        检测公告板中的潜在冲突

        返回冲突列表, 每个冲突: {type, severity, message}
        检测项:
        - API路径不一致
        - 重复文件名
        - 互相矛盾的描述
        """
        content = self.read()
        if not content.strip():
            return []

        conflicts = []

        # 简单启发式检测
        import re

        # 检查是否有AI报告了问题
        if "冲突" in content or "不一致" in content or "⚠" in content:
            conflicts.append({
                "type": "self_report",
                "severity": "warning",
                "message": "公告板中有AI标记了冲突或不一致, 请检查"
            })

        # 检查是否有多个AI声明要写同名文件
        file_mentions = re.findall(r'文件[：:]?\s*[`]?(\w+\.\w+)[`]?', content)
        if len(file_mentions) != len(set(file_mentions)):
            from collections import Counter
            dupes = [f for f, c in Counter(file_mentions).items() if c > 1]
            conflicts.append({
                "type": "duplicate_file",
                "severity": "warning",
                "message": f"多个AI提到了相同文件: {', '.join(dupes)}"
            })

        # 检查API路径是否一致 (前端fetch和后端route)
        frontend_urls = set(re.findall(r'["\'](/api/\S+)["\']', content))
        backend_urls = set(re.findall(r'@\w+_bp\.route\(["\']([^"\']+)["\']', content))
        if frontend_urls and backend_urls:
            unmatched = frontend_urls - backend_urls
            if unmatched:
                conflicts.append({
                    "type": "api_mismatch",
                    "severity": "warning",
                    "message": f"前端调用了后端未定义的API: {', '.join(unmatched)}"
                })

        return conflicts

    def clear(self):
        """清空公告板"""
        with FileLock(BOARD_FILE):
            with open(BOARD_FILE, "w", encoding="utf-8") as f:
                f.write("# AI协作公告板\n\n> 所有AI在此留言, 协调工作\n\n---\n\n")


# 全局单例
board = Board()
