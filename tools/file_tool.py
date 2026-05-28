"""
FileOperationTool - 文件读写/分析工具

模块2: 封装 workspace 为 CrewAI 标准接口

适配角色: 所有AI (按 role 隔离工作目录)
功能: 读文件、写文件、列目录、分析文件结构、跨文件引用检测
"""
import os
from typing import Type, Literal
from pydantic import BaseModel, Field
from tools.base import ClaudeBaseTool
from core.workspace import workspace
from config import WORKSPACE_DIR


class FileOpArgs(BaseModel):
    """文件操作工具入参"""
    operation: str = Field(description="操作类型: read(读文件) | write(写文件) | list(列目录) | analyze(分析结构)")
    role: str = Field(default="frontend", description="角色目录: frontend/backend/tests")
    filename: str = Field(default="", description="文件名 (read/write 时必填)")
    content: str = Field(default="", description="文件内容 (write 时必填)")


class FileOperationTool(ClaudeBaseTool):
    """
    文件操作工具

    封装 workspace 的读写能力, 增加结构分析和跨文件引用检测。

    适配角色: 所有AI角色 (按 role 自动隔离到对应工作区子目录)
    """

    name: str = "file_operation"
    description: str = (
        "文件读写和分析工具。入参: operation(操作类型: read/write/list/analyze), "
        "role(角色目录: frontend/backend/tests), filename(文件名), content(要写入的内容)。"
        "写文件时自动保存到 workspace/<role>/<filename>。"
    )
    args_schema: Type[BaseModel] = FileOpArgs
    allowed_roles: list[str] = []  # 空 = 所有角色可用
    tool_category: str = "file_ops"

    def _execute(
        self,
        operation: str = "list",
        role: str = "frontend",
        filename: str = "",
        content: str = ""
    ) -> str:
        """执行文件操作"""

        if operation == "read":
            return self._read_file(role, filename)

        elif operation == "write":
            return self._write_file(role, filename, content)

        elif operation == "list":
            return self._list_files()

        elif operation == "analyze":
            return self._analyze(role, filename)

        else:
            return f"[错误] 不支持的操作类型: '{operation}'。支持: read, write, list, analyze"

    def _read_file(self, role: str, filename: str) -> str:
        """读取文件"""
        if not filename:
            return "[错误] read 操作需要指定 filename 参数"
        content = workspace.read_file(role, filename)
        if not content:
            return f"[文件不存在] workspace/{role}/{filename}"
        return f"[文件内容] workspace/{role}/{filename}\n```\n{content[:3000]}\n```"

    def _write_file(self, role: str, filename: str, content: str) -> str:
        """写入文件"""
        if not filename or not content:
            return "[错误] write 操作需要指定 filename 和 content 参数"
        filepath = workspace.write_file(role, filename, content)
        return f"[写入成功] {filepath} ({len(content)} 字符)"

    def _list_files(self) -> str:
        """列出所有文件"""
        tree = workspace.list_files()
        if not tree:
            return "[空] 工作区暂无文件"
        lines = ["[工作区文件列表]"]
        for group in tree:
            lines.append(f"\n  [{group['role_name']}]")
            for f in group.get("files", []):
                lines.append(f"    - {f['name']} ({f['size']} 字节)")
        return "\n".join(lines)

    def _analyze(self, role: str, filename: str) -> str:
        """分析文件结构"""
        if not filename:
            return "[错误] analyze 操作需要指定 filename 参数"

        content = workspace.read_file(role, filename)
        if not content:
            return f"[文件不存在] workspace/{role}/{filename}"

        lines = content.split("\n")
        total_lines = len(lines)
        total_chars = len(content)

        # 统计函数/类定义
        import re
        functions = re.findall(r'(?:def |function |class )(\w+)', content)
        imports = re.findall(r'^(?:import |from |require\(|<!-- )', content, re.MULTILINE)

        # 检测跨文件引用
        refs = re.findall(r'(?:src|href|import |require\()["\']([^"\']+)["\']', content)

        return (
            f"[文件分析] workspace/{role}/{filename}\n"
            f"  总行数: {total_lines}\n"
            f"  总字符: {total_chars}\n"
            f"  函数/类: {', '.join(functions) if functions else '无'}\n"
            f"  依赖导入: {len(imports)} 处\n"
            f"  外部引用: {', '.join(refs[:10]) if refs else '无'}"
        )


# 工具实例
file_operation_tool = FileOperationTool()
