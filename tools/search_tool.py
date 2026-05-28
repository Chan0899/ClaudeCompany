"""
TechSearchTool - 技术搜索工具

模块2: 封装 llm_client.chat() + 文件搜索为技术检索能力

适配角色: 所有AI
功能: 代码搜索、技术方案查询、依赖分析、问题排查
"""
import os
from typing import Type
from pydantic import BaseModel, Field
from tools.base import ClaudeBaseTool
from core.llm_client import llm_client
from core.workspace import workspace
from config import WORKSPACE_DIR


class SearchArgs(BaseModel):
    """技术搜索工具入参"""
    query: str = Field(description="搜索关键词或技术问题")
    search_type: str = Field(
        default="code",
        description="搜索类型: code(代码搜索) | tech(技术方案) | deps(依赖分析) | debug(问题排查)"
    )
    context: str = Field(default="", description="附加上下文 (如当前项目信息)")


class TechSearchTool(ClaudeBaseTool):
    """
    技术搜索工具

    封装 Claude 搜索能力和本地文件 grep 为统一检索接口。

    适配角色: 所有AI角色
    """

    name: str = "tech_search"
    description: str = (
        "技术搜索工具。支持代码搜索、技术方案查询、依赖分析、问题排查。"
        "入参: query(搜索问题), search_type(类型: code/tech/deps/debug), context(上下文)。"
    )
    args_schema: Type[BaseModel] = SearchArgs
    allowed_roles: list[str] = []  # 空 = 所有角色
    tool_category: str = "search"

    def _execute(
        self,
        query: str = "",
        search_type: str = "code",
        context: str = ""
    ) -> str:
        """执行技术搜索"""

        if search_type == "code":
            return self._code_search(query, context)
        elif search_type == "tech":
            return self._tech_search(query, context)
        elif search_type == "deps":
            return self._dep_analysis(query, context)
        elif search_type == "debug":
            return self._debug_search(query, context)
        else:
            return f"[错误] 不支持的搜索类型: '{search_type}'。支持: code, tech, deps, debug"

    def _code_search(self, query: str, context: str) -> str:
        """代码搜索: 在 workspace 中搜索相关代码"""
        all_files = workspace.list_all_code_files()
        matches = []

        query_lower = query.lower()
        for role, files in all_files.items():
            for fpath in files:
                try:
                    content = open(fpath, "r", encoding="utf-8").read()
                    if query_lower in content.lower():
                        fname = os.path.basename(fpath)
                        # 找到关键词所在行
                        for i, line in enumerate(content.split("\n"), 1):
                            if query_lower in line.lower():
                                matches.append(f"  [{role}] {fname}:{i} → {line.strip()[:120]}")
                                if len(matches) >= 20:
                                    break
                        if len(matches) >= 20:
                            break
                except Exception:
                    pass
            if len(matches) >= 20:
                break

        if matches:
            return f"[代码搜索结果] 关键词 '{query}':\n" + "\n".join(matches)
        return f"[代码搜索] 未找到包含 '{query}' 的代码。尝试扩大搜索范围或换个关键词。"

    def _tech_search(self, query: str, context: str) -> str:
        """技术方案查询: 通过 Claude 获取技术建议"""
        prompt = (
            f"请对以下技术问题进行简短回答 (200字以内):\n\n"
            f"【问题】{query}\n"
        )
        if context:
            prompt += f"\n【项目上下文】{context}\n"
        prompt += "\n请给出最直接的方案建议或代码示例。"

        result = llm_client.chat(prompt=prompt, timeout=60)
        if result["success"]:
            return f"[技术搜索] {result['reply'][:2000]}"
        return f"[技术搜索失败] {result.get('error', '未知错误')}"

    def _dep_analysis(self, query: str, context: str) -> str:
        """依赖分析: 检查项目文件间的依赖关系"""
        all_files = workspace.list_all_code_files()

        # 搜索 import/require 引用
        import re
        dep_map: dict[str, list[str]] = {}
        for role, files in all_files.items():
            for fpath in files:
                fname = os.path.basename(fpath)
                try:
                    content = open(fpath, "r", encoding="utf-8").read()
                    refs = re.findall(r'(?:import |from |require\()["\'/]*(\w+)["\'/]', content)
                    dep_map[fname] = [r for r in refs if r not in ("__future__", "os", "sys", "re", "json", "typing")]
                except Exception:
                    pass

        lines = [f"[依赖分析] 文件间引用关系:"]
        for fname, deps in dep_map.items():
            if deps:
                lines.append(f"  {fname} → {', '.join(deps)}")

        if len(lines) == 1:
            lines.append("  未检测到明显依赖关系")
        return "\n".join(lines)

    def _debug_search(self, query: str, context: str) -> str:
        """问题排查: 搜索错误信息并提供修复建议"""
        # 复用 Claude 进行错误分析
        prompt = (
            f"请快速分析以下技术问题 (100字以内):\n\n"
            f"【问题】{query}\n"
        )
        if context:
            prompt += f"\n【代码上下文】{context}\n"
        prompt += "\n请给出: 1) 可能原因 2) 修复方向"

        result = llm_client.chat(prompt=prompt, timeout=60)
        if result["success"]:
            return f"[问题排查] {result['reply'][:2000]}"
        return f"[排查失败] {result.get('error', '未知错误')}"


# 工具实例
tech_search_tool = TechSearchTool()
