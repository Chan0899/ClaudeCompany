"""
ClaudeCodeTool - 代码执行工具

模块2: 封装 llm_client.chat_stream() 为 CrewAI 标准工具

适配角色: frontend_dev, backend_dev
功能: 接收任务描述, 调用 Claude 生成代码, 输出到 workspace
"""
import os
from typing import Type
from pydantic import BaseModel, Field
from tools.base import ClaudeBaseTool
from core.llm_client import llm_client
from core.workspace import workspace
from config import WORKSPACE_DIR


class CodeGenArgs(BaseModel):
    """代码生成工具入参"""
    task_description: str = Field(description="代码任务描述, 越具体越好")
    language: str = Field(default="html", description="目标语言: html/css/js/python")
    context: str = Field(default="", description="额外上下文 (如API签名、设计规范)")
    output_filename: str = Field(default="output", description="输出文件名 (不含路径)")


class ClaudeCodeTool(ClaudeBaseTool):
    """
    Claude 代码执行工具

    调用 Claude Code 生成完整可运行代码, 自动保存到 workspace。

    适配角色: 前端开发AI(frontend_dev), 后端开发AI(backend_dev)
    """

    name: str = "claude_code_executor"
    description: str = (
        "调用Claude Code生成代码。入参: task_description(任务描述), "
        "language(目标语言), context(额外上下文), output_filename(输出文件名)。"
        "返回生成的代码内容及保存路径。"
    )
    args_schema: Type[BaseModel] = CodeGenArgs
    allowed_roles: list[str] = ["frontend_dev", "backend_dev"]
    tool_category: str = "code_gen"

    def _execute(
        self,
        task_description: str = "",
        language: str = "html",
        context: str = "",
        output_filename: str = "output"
    ) -> str:
        """执行代码生成任务"""

        # 确定工作目录
        role_subdir = "frontend" if language in ("html", "css", "js") else "backend"
        role_dir = os.path.join(WORKSPACE_DIR, role_subdir)
        os.makedirs(role_dir, exist_ok=True)

        # 构建提示词
        prompt = (
            f"请完成以下代码开发任务:\n\n"
            f"【任务】{task_description}\n"
            f"【语言】{language}\n"
            f"【输出文件】{output_filename}\n"
        )
        if context:
            prompt += f"\n【额外上下文】\n{context}\n"
        prompt += (
            f"\n要求:\n"
            f"1. 生成完整、可直接运行的代码, 不要省略任何部分\n"
            f"2. 将代码保存到 {role_dir}/{output_filename}\n"
            f"3. 代码中添加适当的中文注释\n"
            f"4. 完成后简要说明生成了什么文件\n"
        )

        output_lines: list[str] = []

        # 流式调用 Claude
        result = llm_client.chat_stream(
            prompt=prompt,
            system_prompt=f"你是一个资深{language}开发工程师。生成高质量、完整的代码。",
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
            cwd=role_dir,
            timeout=300,
            on_line=lambda line: output_lines.append(line)
        )

        # 检测产出文件
        output_path = os.path.join(role_dir, output_filename)
        if os.path.exists(output_path):
            size = os.path.getsize(output_path)
            return (
                f"[代码执行完成] 文件已生成: {output_path} ({size} 字节)\n"
                f"输出摘要: {' '.join(output_lines[-5:]) if output_lines else '无'}"
            )
        else:
            new_files = [
                f for f in os.listdir(role_dir)
                if not f.startswith("_") and not f.endswith((".tmp", ".ps1", ".lock"))
            ]
            if new_files:
                return f"[代码执行完成] 产出文件: {', '.join(new_files)}"
            return f"[代码执行完成] 未检测到新文件。Claude 输出:\n{' '.join(output_lines[-10:])}"


# 工具实例
claude_code_tool = ClaudeCodeTool()
