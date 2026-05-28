"""
ToolRegistry - 工具注册中心

模块2: Claude Code专属Tool层增量封装

功能:
  1. 工具注册/注销 (可插拔)
  2. 按角色查询可用工具
  3. 权限校验
  4. 全量工具列表
"""
from typing import Optional
from tools.base import ClaudeBaseTool


class ToolRegistry:
    """
    工具注册中心 (全局单例)

    用法:
      from tools.code_tool import claude_code_tool
      tool_registry.register(claude_code_tool)
      tools = tool_registry.get_tools_for_role("frontend_dev")
    """

    def __init__(self):
        self._tools: dict[str, ClaudeBaseTool] = {}

    # ============================================================
    # 注册 / 注销
    # ============================================================

    def register(self, tool: ClaudeBaseTool):
        """注册一个工具"""
        if tool.name in self._tools:
            raise ValueError(f"工具 '{tool.name}' 已注册, 不允许重复")
        self._tools[tool.name] = tool

    def unregister(self, name: str):
        """注销一个工具"""
        self._tools.pop(name, None)

    # ============================================================
    # 查询
    # ============================================================

    def get_tool(self, name: str) -> Optional[ClaudeBaseTool]:
        """按名称获取工具"""
        return self._tools.get(name)

    def get_tools_for_role(self, role_id: str) -> list[ClaudeBaseTool]:
        """
        返回指定角色可用的工具列表

        规则: 如果工具的 allowed_roles 为空, 所有角色都可用
              否则只返回 allowed_roles 中包含该 role_id 的工具
        """
        result = []
        for tool in self._tools.values():
            if not tool.allowed_roles or role_id in tool.allowed_roles:
                result.append(tool)
        return result

    def get_tools_by_category(self, category: str) -> list[ClaudeBaseTool]:
        """按类别查询工具"""
        return [t for t in self._tools.values() if t.tool_category == category]

    def list_all(self) -> list[dict]:
        """列出所有已注册工具的基本信息"""
        return [t.role_info for t in self._tools.values()]

    def can_use(self, tool_name: str, role_id: str) -> bool:
        """检查指定角色是否有权使用某工具"""
        tool = self._tools.get(tool_name)
        if not tool:
            return False
        if not tool.allowed_roles:
            return True
        return role_id in tool.allowed_roles

    @property
    def count(self) -> int:
        """已注册工具数量"""
        return len(self._tools)


# ============================================================
# 全局单例
# ============================================================
tool_registry = ToolRegistry()
