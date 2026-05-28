"""
tools - Claude Code 专属 Tool 层

模块2: 基于 CrewAI 标准 Tool 接口, 封装 Claude Code 能力为可插拔工具

四大工具:
  1. ClaudeCodeTool - 代码执行
  2. FileOperationTool - 文件读写/分析
  3. TechSearchTool - 技术搜索
  4. DebugAnalyzerTool - 调试/报错解析

使用方式:
  from tools import tool_registry
  from tools.code_tool import claude_code_tool
  tool_registry.register(claude_code_tool)
  tools = tool_registry.get_tools_for_role("frontend_dev")
"""
from tools.base import ClaudeBaseTool
from tools.registry import ToolRegistry, tool_registry
from tools.code_tool import claude_code_tool
from tools.file_tool import file_operation_tool
from tools.search_tool import tech_search_tool
from tools.debug_tool import debug_analyzer_tool

# 自动注册所有默认工具
_tools_to_register = [
    claude_code_tool,
    file_operation_tool,
    tech_search_tool,
    debug_analyzer_tool,
]

for _t in _tools_to_register:
    try:
        tool_registry.register(_t)
    except ValueError:
        pass  # 已注册则跳过

__all__ = [
    "ClaudeBaseTool",
    "ToolRegistry",
    "tool_registry",
    "claude_code_tool",
    "file_operation_tool",
    "tech_search_tool",
    "debug_analyzer_tool",
]
