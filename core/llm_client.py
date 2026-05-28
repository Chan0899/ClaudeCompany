"""
全局Claude模型客户端 - 统一封装Claude CLI调用

模块1: 环境适配 & Claude全局模型兼容升级

功能:
  1. 封装 claude -p 调用, 统一入参出参
  2. 支持 claude/simulated 双模式
  3. 统一错误处理、超时控制、日志记录
  4. 全局单例, 供所有模块使用
"""
import os
import time
import subprocess
import threading
from typing import Iterator, Callable
from config import AI_MODE, CLAUDE_MODEL


class ClaudeClient:
    """
    Claude Code 全局客户端

    封装所有对 Claude CLI 的调用, 提供:
      - chat(): 同步对话 (替代 subprocess.run)
      - chat_stream(): 流式对话 (替代 subprocess.Popen + 逐行读取)
      - 模拟模式: 开发调试时无需真实 Claude CLI
    """

    def __init__(self):
        self._model = CLAUDE_MODEL
        self._mode = AI_MODE

    # ============================================================
    # 同步对话 (用于管理AI对话)
    # ============================================================

    def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        allowed_tools: list[str] | None = None,
        cwd: str = None,
        timeout: int = 180,
        memory_context: str = ""
    ) -> dict:
        """
        同步调用 Claude, 返回完整响应

        参数:
          prompt: 用户提示词 (包含对话历史等)
          system_prompt: 系统提示词 (角色设定)
          allowed_tools: 允许的工具列表, 如 ["Read", "Glob", "Grep"]
          cwd: 工作目录
          timeout: 超时秒数

        返回:
          {"success": bool, "reply": str, "error": str|None}
        """
        if self._mode == "simulated":
            return self._simulated_chat(prompt, system_prompt)

        # 注入记忆上下文
        final_prompt = prompt
        if memory_context:
            final_prompt = memory_context + "\n\n---\n\n" + prompt

        return self._claude_chat(final_prompt, system_prompt, allowed_tools, cwd, timeout)

    def _claude_chat(
        self,
        prompt: str,
        system_prompt: str,
        allowed_tools: list[str] | None,
        cwd: str | None,
        timeout: int
    ) -> dict:
        """真实调用 claude CLI (同步)"""
        if allowed_tools is None:
            allowed_tools = ["Read", "Glob", "Grep"]

        cmd = [
            "claude", "-p", prompt,
            "--dangerously-skip-permissions",
            "--allowedTools", ",".join(allowed_tools)
        ]
        if system_prompt:
            cmd.extend(["--append-system-prompt", system_prompt])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd or os.getcwd(),
                encoding="utf-8"
            )
            reply = result.stdout.strip()
            if not reply and result.stderr:
                reply = f"[Claude返回为空] stderr: {result.stderr[:200]}"
            return {"success": True, "reply": reply, "error": None}
        except subprocess.TimeoutExpired:
            return {"success": False, "reply": "", "error": f"Claude调用超时 ({timeout}s)"}
        except FileNotFoundError:
            return {"success": False, "reply": "", "error": "claude CLI 未找到, 请确认已安装 Claude Code"}
        except Exception as e:
            return {"success": False, "reply": "", "error": str(e)}

    # ============================================================
    # 流式对话 (用于后台执行AI, SSE实时推送)
    # ============================================================

    def chat_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        allowed_tools: list[str] | None = None,
        cwd: str = None,
        timeout: int = 300,
        on_line: Callable[[str], None] = None,
        on_error: Callable[[str], None] = None,
        memory_context: str = ""
    ) -> dict:
        """
        流式调用 Claude, 逐行回调

        参数:
          prompt: 任务提示词
          system_prompt: 角色系统提示词
          allowed_tools: 允许的工具列表
          cwd: 工作目录
          timeout: 超时秒数
          on_line: 每行输出的回调 (用于SSE推送)
          on_error: 错误回调

        返回:
          {"success": bool, "returncode": int, "error": str|None}
        """
        if self._mode == "simulated":
            return self._simulated_stream(prompt, system_prompt, on_line)

        # 注入记忆上下文
        final_prompt = prompt
        if memory_context:
            final_prompt = memory_context + "\n\n---\n\n" + prompt

        return self._claude_stream(
            final_prompt, system_prompt, allowed_tools, cwd, timeout, on_line, on_error
        )

    def _claude_stream(
        self,
        prompt: str,
        system_prompt: str,
        allowed_tools: list[str] | None,
        cwd: str | None,
        timeout: int,
        on_line: Callable[[str], None] | None,
        on_error: Callable[[str], None] | None
    ) -> dict:
        """真实调用 claude CLI (流式)"""
        if allowed_tools is None:
            allowed_tools = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]

        cmd = [
            "claude", "-p", prompt,
            "--dangerously-skip-permissions",
            "--allowedTools", ",".join(allowed_tools)
        ]
        if system_prompt:
            cmd.extend(["--append-system-prompt", system_prompt])

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                cwd=cwd or os.getcwd(),
                bufsize=1
            )

            for line in iter(proc.stdout.readline, ""):
                if line.strip():
                    if on_line:
                        on_line(line.strip())

            proc.wait(timeout=timeout)
            stderr_text = proc.stderr.read()
            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "error": stderr_text[:500] if proc.returncode != 0 else None
            }

        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
            if on_error:
                on_error(f"任务超时({timeout}秒), 已终止")
            return {"success": False, "returncode": -1, "error": "超时"}
        except FileNotFoundError:
            if on_error:
                on_error("claude CLI 未找到")
            return {"success": False, "returncode": -1, "error": "claude CLI not found"}
        except Exception as e:
            if on_error:
                on_error(str(e))
            return {"success": False, "returncode": -1, "error": str(e)}

    # ============================================================
    # 模拟模式 (simulated) - 无需真实Claude CLI
    # ============================================================

    def _simulated_chat(self, prompt: str, system_prompt: str) -> dict:
        """模拟同步对话: 返回固定占位响应"""
        time.sleep(0.3)
        # 检测快捷测试
        if "登录" in prompt:
            reply = (
                "收到需求, 我来安排团队实现登录功能。\n\n"
                "登录功能需要前后端配合: 前端做登录表单页面, 后端做认证API接口。\n"
                "我现在派出前端和后端同时开工。\n\n"
                "<<<DELEGATE>>>\n"
                '{"tasks": ['
                '{"role": "frontend_dev", "description": "创建用户登录页面, 包含用户名密码输入框、表单验证、登录按钮, 文件: login.html"},'
                '{"role": "backend_dev", "description": "创建登录认证API /api/auth/login, 支持POST请求, 验证用户名密码, 返回token, 文件: auth_api.py"}'
                ']}\n'
                "<<<END>>>"
            )
        elif "数据" in prompt or "列表" in prompt:
            reply = (
                "明白了, 数据管理需求。我派出前端和后端来处理。\n\n"
                "<<<DELEGATE>>>\n"
                '{"tasks": ['
                '{"role": "frontend_dev", "description": "创建数据管理列表页面, 包含表格展示、编辑删除按钮, 文件: list.html"},'
                '{"role": "backend_dev", "description": "创建数据管理API, 包含CRUD接口, 文件: data_api.py"},'
                '{"role": "tester", "description": "编写数据管理功能的测试用例, 文件: test_data.py"}'
                ']}\n'
                "<<<END>>>"
            )
        elif "注册" in prompt:
            reply = (
                "用户注册功能, 需要前后端配合。现在派出团队。\n\n"
                "<<<DELEGATE>>>\n"
                '{"tasks": ['
                '{"role": "frontend_dev", "description": "创建用户注册页面, 包含注册表单和验证, 文件: register.html"},'
                '{"role": "backend_dev", "description": "创建注册API /api/auth/register, 文件: register_api.py"}'
                ']}\n'
                "<<<END>>>"
            )
        else:
            reply = (
                f"收到你的需求: 「{prompt[:80]}...」\n\n"
                "这是一个通用需求, 我派出前端和后端来处理。"
            )
        return {"success": True, "reply": reply, "error": None}

    def _simulated_stream(
        self,
        prompt: str,
        system_prompt: str,
        on_line: Callable[[str], None] | None
    ) -> dict:
        """模拟流式对话: 输出模拟代码生成过程"""
        import random
        lines = [
            "正在分析需求...",
            "需求分析完成, 开始编写代码。",
            "正在生成代码结构...",
            "代码生成中...",
            "代码编写完成。",
            "生成文件: output.html"
        ]
        for line in lines:
            time.sleep(random.uniform(0.5, 1.0))
            if on_line:
                on_line(line)
        return {"success": True, "returncode": 0, "error": None}

    # ============================================================
    # 工具方法
    # ============================================================

    @property
    def mode(self) -> str:
        """当前运行模式"""
        return self._mode

    @property
    def model(self) -> str:
        """当前模型"""
        return self._model


# ============================================================
# 全局单例
# ============================================================
llm_client = ClaudeClient()
