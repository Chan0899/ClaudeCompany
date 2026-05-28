"""
DebugAnalyzerTool - 代码调试/报错解析工具

模块2: 封装 llm_client.chat() 为调试专用工具

适配角色: tester (主), 其他角色只读
功能: 错误堆栈分析、根因定位、修复建议、代码审查
"""
import os
from typing import Type
from pydantic import BaseModel, Field
from tools.base import ClaudeBaseTool
from core.llm_client import llm_client
from core.workspace import workspace
from config import WORKSPACE_DIR


class DebugArgs(BaseModel):
    """调试分析工具入参"""
    error_message: str = Field(description="错误信息或堆栈跟踪")
    code_context: str = Field(default="", description="相关代码片段 (可选, 自动从 workspace 搜索)")
    language: str = Field(default="python", description="代码语言: python/html/js/css")


class DebugAnalyzerTool(ClaudeBaseTool):
    """
    调试分析工具

    分析错误堆栈、定位根因、生成修复建议。
    会自动从 workspace 中搜索相关代码作为分析上下文。

    适配角色: 测试AI(tester) 专用
    """

    name: str = "debug_analyzer"
    description: str = (
        "代码调试和报错解析工具。入参: error_message(错误信息), "
        "code_context(相关代码可选), language(语言)。"
        "返回根因分析和修复建议。"
    )
    args_schema: Type[BaseModel] = DebugArgs
    allowed_roles: list[str] = ["tester"]  # 仅测试AI
    tool_category: str = "debug"

    def _execute(
        self,
        error_message: str = "",
        code_context: str = "",
        language: str = "python"
    ) -> str:
        """执行调试分析"""

        # 如果没有提供 code_context, 尝试从 workspace 自动搜索
        if not code_context:
            code_context = self._search_relevant_code(error_message)

        # 构建分析提示词
        prompt = (
            f"你是资深{language}调试专家。请分析以下错误:\n\n"
            f"【错误信息】\n{error_message}\n\n"
        )
        if code_context:
            prompt += f"【相关代码】\n{code_context}\n\n"
        prompt += (
            f"请按以下格式回复:\n"
            f"## 根因分析\n(一句话定位根本原因)\n\n"
            f"## 严重程度\ncritical/high/medium/low\n\n"
            f"## 修复方案\n(具体的代码修改建议)\n\n"
            f"## 预防措施\n(如何避免类似问题)\n"
        )

        result = llm_client.chat(
            prompt=prompt,
            system_prompt=f"你是资深{language}代码调试专家。分析精准、建议实用。",
            timeout=120
        )

        if result["success"]:
            return f"[调试分析结果]\n{result['reply'][:3000]}"
        return f"[分析失败] {result.get('error', '未知错误')}"

    def _search_relevant_code(self, error_message: str) -> str:
        """从 workspace 中搜索与错误相关的代码"""
        all_files = workspace.list_all_code_files()
        snippets: list[str] = []

        # 提取错误中的关键词 (文件名、函数名、类名)
        import re
        keywords = re.findall(r'(?:File "|in |class |def )([\w.]+)', error_message)
        keywords = list(set(k for k in keywords if len(k) > 2))[:5]

        if not keywords:
            return ""

        for role, files in all_files.items():
            for fpath in files:
                try:
                    content = open(fpath, "r", encoding="utf-8").read()
                    for kw in keywords:
                        if kw.lower() in content.lower():
                            fname = os.path.basename(fpath)
                            snippets.append(f"// {fname}\n{content[:1000]}")
                            break
                except Exception:
                    pass
                if len(snippets) >= 3:
                    break
            if len(snippets) >= 3:
                break

        return "\n\n".join(snippets)


# 工具实例
debug_analyzer_tool = DebugAnalyzerTool()
