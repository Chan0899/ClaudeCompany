"""
QualityChecker - 代码结果自动质控

模块8: 对AI产出代码做自动化质量检查

复用:
  - workspace.list_files() / workspace.read_file()
  - board.detect_conflicts()
"""

import os
import re
from config import WORKSPACE_DIR
from core.workspace import workspace
from core.event_bus import event_bus


class QualityChecker:
    """
    自动质控, 在任务完成/审批时运行

    检查项:
      1. 文件存在性 - 分配的角色是否产出了文件
      2. API一致性 - 前端fetch路径 vs 后端route路径
      3. 文件内容 - 不含空文件或占位符
    """

    def __init__(self):
        self._issues: list[dict] = []

    # ============================================================
    # 各项检查
    # ============================================================

    def check_files_exist(self, roles: list[str]) -> list[dict]:
        """
        检查指定角色是否产出了文件

        返回: [{"role": "frontend_dev", "has_files": True, "files": ["a.html"]}, ...]
        """
        results = []
        role_dir_map = {
            "frontend_dev": "frontend",
            "backend_dev": "backend",
            "tester": "tests",
        }
        for role in roles:
            subdir = role_dir_map.get(role, role)
            role_dir = os.path.join(WORKSPACE_DIR, subdir)
            files = []
            if os.path.exists(role_dir):
                files = [
                    f for f in os.listdir(role_dir)
                    if not f.startswith("_") and not f.endswith((".tmp", ".ps1", ".lock"))
                    and os.path.isfile(os.path.join(role_dir, f))
                ]
            has_files = len(files) > 0
            if not has_files:
                self._issues.append({
                    "type": "missing_output",
                    "severity": "high",
                    "role": role,
                    "message": f"角色 {role} 未产出任何文件"
                })
            results.append({"role": role, "has_files": has_files, "files": files})
        return results

    def check_api_consistency(self) -> list[dict]:
        """
        交叉检查前端 fetch 路径 与 后端 route 路径

        从前端 HTML 文件提取 fetch/api 调用,
        从后端 Python 文件提取 @route 装饰器路径, 检查是否匹配
        """
        issues = []

        # 提取前端调用的API路径
        frontend_urls = set()
        for fname in self._list_role_files("frontend"):
            content = workspace.read_file("frontend", fname)
            urls = re.findall(r"""fetch\s*\(\s*['"]([^'"]+)['"]""", content)
            urls += re.findall(r"""['"](/api/[^'"]+)['"]""", content)
            frontend_urls.update(urls)

        # 提取后端定义的路径
        backend_routes = set()
        for fname in self._list_role_files("backend"):
            content = workspace.read_file("backend", fname)
            routes = re.findall(r"""@\w+\.route\s*\(\s*['"]([^'"]+)['"]""", content)
            backend_routes.update(routes)

        # 纯路径匹配
        frontend_paths = {u for u in frontend_urls if u.startswith("/")}
        backend_paths = backend_routes

        # 检查前端调用了后端未定义的路由
        unmatched = frontend_paths - backend_paths
        for path in unmatched:
            issues.append({
                "type": "api_mismatch",
                "severity": "medium",
                "frontend_calls": path,
                "message": f"前端调用了后端未定义的API: {path}"
            })

        for issue in issues:
            self._issues.append(issue)

        return issues

    def check_file_content(self) -> list[dict]:
        """
        检查文件内容质量: 不为空、不含明显占位符
        """
        issues = []
        placeholders = ["TODO: implement", "your code here", "placeholder", "// TODO"]

        for role in ["frontend", "backend", "tests"]:
            for fname in self._list_role_files(role):
                content = workspace.read_file(role, fname)
                if not content.strip():
                    issues.append({
                        "type": "empty_file",
                        "severity": "high",
                        "file": f"workspace/{role}/{fname}",
                        "message": f"文件为空: {role}/{fname}"
                    })
                    self._issues.append(issues[-1])
                    continue

                for ph in placeholders:
                    if ph.lower() in content.lower()[:500]:
                        issues.append({
                            "type": "placeholder_content",
                            "severity": "low",
                            "file": f"workspace/{role}/{fname}",
                            "message": f"文件含占位符 '{ph}': {role}/{fname}"
                        })
                        self._issues.append(issues[-1])
                        break

        return issues

    def run_all_checks(self, roles: list[str] | None = None) -> dict:
        """
        运行全部检查, 返回完整质控报告

        返回:
          {
            "passed": bool,
            "issue_count": int,
            "high_severity": int,
            "checks": {...},
            "issues": [...]
          }
        """
        self._issues = []
        if roles is None:
            roles = ["frontend_dev", "backend_dev", "tester"]

        files_result = self.check_files_exist(roles)
        api_result = self.check_api_consistency()
        content_result = self.check_file_content()

        # 也可以调用已有的公告板冲突检测
        from core.bulletin_board import board
        board_conflicts = board.detect_conflicts()
        for c in board_conflicts:
            self._issues.append({
                "type": c.get("type", "board_conflict"),
                "severity": c.get("severity", "warning"),
                "message": c.get("message", ""),
            })

        high_count = sum(1 for i in self._issues if i.get("severity") == "high")
        passed = high_count == 0

        report = {
            "passed": passed,
            "issue_count": len(self._issues),
            "high_severity": high_count,
            "checks": {
                "files_exist": files_result,
                "api_consistency": api_result,
                "file_content": content_result,
                "board_conflicts": board_conflicts,
            },
            "issues": self._issues,
        }

        # 发布质控结果到事件总线
        event_bus.publish("quality_check", report)

        return report

    @property
    def issues(self) -> list[dict]:
        return self._issues

    def _list_role_files(self, role: str) -> list[str]:
        """列出指定角色目录下的文件"""
        role_dir = os.path.join(WORKSPACE_DIR, role)
        if not os.path.exists(role_dir):
            return []
        return [
            f for f in os.listdir(role_dir)
            if not f.startswith("_") and not f.endswith((".tmp", ".ps1", ".lock"))
            and os.path.isfile(os.path.join(role_dir, f))
        ]


# 全局单例
quality_checker = QualityChecker()
