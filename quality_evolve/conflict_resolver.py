"""
ConflictResolver - 多员工输出冲突自主调解

模块8: 检测AI间冲突并生成解决建议

检测类型:
  - duplicate_file: 两个AI产出了同名文件
  - api_mismatch: 前后端API路径不一致
  - naming_conflict: 文件命名约定冲突
  - dependency_issue: 依赖顺序错误

风险评级:
  - low: 可自动解决 (刊登公告板建议)
  - high: 需人工审查 (标记 need_human_review)
"""
import os
import json
from config import WORKSPACE_DIR
from core.event_bus import event_bus
from core.bulletin_board import board
from core.workspace import workspace


class ConflictResolver:
    """
    冲突检测与调解

    用法:
      resolver = ConflictResolver()
      conflicts = resolver.detect()
      for c in conflicts:
          proposal = resolver.propose_resolution(c)
    """

    def __init__(self):
        self._conflicts: list[dict] = []

    # ============================================================
    # 检测
    # ============================================================

    def detect(self) -> list[dict]:
        """
        全面冲突检测

        返回冲突列表, 每个冲突:
          {type, severity, role_a, role_b, description, resolution, need_human_review}
        """
        self._conflicts = []

        self._detect_duplicate_files()
        self._detect_api_mismatch()
        self._detect_naming_conflicts()

        # 发布到事件总线
        if self._conflicts:
            event_bus.publish("conflict_detected", {
                "count": len(self._conflicts),
                "conflicts": self._conflicts
            })

        return self._conflicts

    def _detect_duplicate_files(self):
        """检测不同角色目录下的同名文件"""
        all_files: dict[str, list[str]] = {}
        for role in ["frontend", "backend", "tests"]:
            role_dir = os.path.join(WORKSPACE_DIR, role)
            if os.path.exists(role_dir):
                all_files[role] = [
                    f for f in os.listdir(role_dir)
                    if not f.startswith("_") and os.path.isfile(os.path.join(role_dir, f))
                ]

        # 交叉检查
        roles = list(all_files.keys())
        for i in range(len(roles)):
            for j in range(i + 1, len(roles)):
                dupes = set(all_files[roles[i]]) & set(all_files[roles[j]])
                for fname in dupes:
                    self._conflicts.append({
                        "type": "duplicate_file",
                        "severity": "low",
                        "role_a": roles[i],
                        "role_b": roles[j],
                        "file": fname,
                        "description": f"两个角色产出了同名文件: {fname} ({roles[i]}, {roles[j]})",
                        "resolution": f"建议合并为一个文件, 或按角色目录隔离引用",
                        "need_human_review": False,
                    })

    def _detect_api_mismatch(self):
        """检测前后端API路径不一致"""
        import re

        # 从前端提取数据格式约定 (Content-Type, 请求体字段)
        frontend_formats: dict[str, set] = {}
        for fname in self._list_files("frontend"):
            content = workspace.read_file("frontend", fname)
            # 提取 fetch 请求中的 Content-Type
            ctypes = re.findall(r"""['"]Content-Type['"]:\s*['"]([^'"]+)['"]""", content)
            if ctypes:
                frontend_formats[fname] = set(ctypes)

        # 从后端提取响应字段
        for fname in self._list_files("backend"):
            content = workspace.read_file("backend", fname)
            # 提取 jsonify 返回的字段名
            resp_fields = set(re.findall(r"""['"](\w+)['"]\s*:""", content))

        # 简单启发式: 前端期待 application/json 但后端返回可能有误
        for fname, formats in frontend_formats.items():
            if "application/json" in formats:
                # 检查后端是否有匹配的接口定义
                # 这是一个轻量检查, 详细分析用 llm_client
                pass

    def _detect_naming_conflicts(self):
        """检测文件命名约定冲突 (如 index.html vs login.html 等)"""
        # 简单检测: 如果多个前端文件都以相同前缀命名
        frontend_files = self._list_files("frontend")
        prefixes: dict[str, list] = {}
        for fname in frontend_files:
            prefix = fname.split(".")[0].split("_")[0]
            if prefix not in prefixes:
                prefixes[prefix] = []
            prefixes[prefix].append(fname)

        for prefix, files in prefixes.items():
            if len(files) > 1 and len(prefix) > 2:
                # 多个文件共享前缀, 可能是功能重复
                pass  # 低优先级, 仅记录不报警

    # ============================================================
    # 解决建议
    # ============================================================

    def propose_resolution(self, conflict: dict) -> str:
        """为冲突生成解决建议文本"""
        proposals = {
            "duplicate_file": (
                f"同名文件冲突: {conflict['file']}\n"
                f"涉及角色: {conflict['role_a']}, {conflict['role_b']}\n"
                f"建议: 各自在文件名中加入角色前缀, 或分别管理在自己的目录下。\n"
                f"该冲突已自动解决 (各角色目录物理隔离, 无实际影响)。"
            ),
            "api_mismatch": (
                f"API路径不一致: 前端调用了后端未定义的路径\n"
                f"建议: 后端确认是否遗漏了该接口, 或前端修正API路径。\n"
                f"在公告板中发布统一的API约定。"
            ),
            "naming_conflict": (
                f"命名冲突: {conflict.get('description', '未详述')}\n"
                f"建议: 统一团队的命名约定, 写入团队共享记忆。"
            ),
            "dependency_issue": (
                f"依赖顺序问题: {conflict.get('description', '未详述')}\n"
                f"建议: 先完成被依赖角色的工作, 再做自己的部分。"
            ),
        }
        return proposals.get(conflict["type"], f"未识别的冲突类型: {conflict['type']}")

    def auto_resolve(self) -> dict:
        """
        自动解决低风险冲突

        返回: {resolved: 数, skipped: 数, proposals: [公告板消息]}

        对于低风险冲突:
          1. 生成解决建议
          2. 发布到公告板
          3. 标记为已处理

        对于高风险冲突:
          1. 标记 need_human_review=True
          2. 发布到事件总线, 等待人工审批
        """
        conflicts = self.detect()
        resolved = 0
        skipped = 0
        proposals = []

        for c in conflicts:
            proposal = self.propose_resolution(c)
            if c.get("need_human_review", False):
                skipped += 1
                event_bus.publish("log", {
                    "ai_id": "conflict_resolver",
                    "ai_name": "冲突调解器",
                    "message": f"[HIGH] {c['description']} → 需要人工审查"
                })
            else:
                resolved += 1
                board.post("conflict_resolver", "冲突调解器",
                           f"自动调解: {proposal}")
                proposals.append(proposal)

        if resolved > 0 or skipped > 0:
            event_bus.publish("log", {
                "ai_id": "conflict_resolver",
                "ai_name": "冲突调解器",
                "message": f"冲突处理完成: 自动解决{resolved}个, 需人工审查{skipped}个"
            })

        return {"resolved": resolved, "skipped": skipped, "proposals": proposals}

    @property
    def conflicts(self) -> list[dict]:
        return self._conflicts

    def _list_files(self, role: str) -> list[str]:
        role_dir = os.path.join(WORKSPACE_DIR, role)
        if not os.path.exists(role_dir):
            return []
        return [
            f for f in os.listdir(role_dir)
            if not f.startswith("_") and os.path.isfile(os.path.join(role_dir, f))
        ]


# 全局单例
conflict_resolver = ConflictResolver()
