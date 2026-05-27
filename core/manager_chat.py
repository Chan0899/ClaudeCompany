"""
管理AI对话引擎 - 通过 claude -p 实现真正的智能对话和任务拆解

流程:
  1. 人类发消息 → 调用 claude -p (管理AI角色)
  2. Claude 回复 → 解析是否包含 <<<DELEGATE>>> 任务拆解
  3. 如果是普通对话 → 返回对话内容给UI
  4. 如果包含拆解 → 解析JSON, 启动执行AI终端
"""
import json
import re
import subprocess
import os
from config import MANAGER_SYSTEM_PROMPT


class ManagerChat:
    """管理AI对话管理: 维护历史, 调用Claude, 解析拆解"""

    def __init__(self):
        self.history: list[dict] = []  # [{"role": "human"/"manager", "content": "..."}]
        self.max_history = 20  # 保留最近20条消息作为上下文

    def chat(self, message: str) -> dict:
        """
        发送消息给管理AI, 返回回复 + 可选的拆解任务

        返回格式:
        {
            "reply": "管理AI的回复文本",
            "delegation": None | {"tasks": [...]},
            "error": None | "错误信息"
        }
        """
        # 记录人类消息
        self.history.append({"role": "human", "content": message})

        # 构建Claude提示词
        prompt = self._build_prompt()

        try:
            # 调用 claude CLI (非交互模式)
            # 管理AI只需要对话能力, 不需要写文件
            result = subprocess.run(
                ["claude", "-p", prompt,
                 "--append-system-prompt", MANAGER_SYSTEM_PROMPT,
                 "--dangerously-skip-permissions",
                 "--allowedTools", "Read,Glob,Grep"],
                capture_output=True,
                text=True,
                timeout=180,
                cwd=os.path.join(os.path.dirname(os.path.dirname(__file__)), "workspace"),
                encoding="utf-8",
            )

            reply = result.stdout.strip()

            # 如果stdout为空但有stderr, 可能出错了
            if not reply and result.stderr:
                reply = f"[Claude返回为空] stderr: {result.stderr[:200]}"

        except subprocess.TimeoutExpired:
            reply = "抱歉, 处理超时。请重新表述你的需求。"
        except FileNotFoundError:
            return {
                "reply": "错误: 找不到claude命令。请确认已安装Claude Code CLI。",
                "delegation": None,
                "error": "claude CLI not found"
            }
        except Exception as e:
            return {
                "reply": f"系统错误: {str(e)}",
                "delegation": None,
                "error": str(e)
            }

        # 解析是否包含任务拆解
        delegation = self._parse_delegation(reply)

        # 如果有拆解, 清理回复中的JSON块 (不显示给人类)
        clean_reply = self._clean_reply(reply)

        # 记录管理AI回复
        self.history.append({"role": "manager", "content": clean_reply})

        # 修剪历史
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

        return {
            "reply": clean_reply,
            "delegation": delegation,
            "error": None
        }

    def _build_prompt(self) -> str:
        """构建包含对话历史的提示词"""
        lines = []
        lines.append("以下是对话历史 (你是管理AI, 对方是人类负责人):\n")

        for msg in self.history:
            if msg["role"] == "human":
                lines.append(f"【人类负责人】: {msg['content']}")
            else:
                lines.append(f"【你(管理AI)】: {msg['content']}")

        lines.append("")
        lines.append("请根据以上对话, 回复人类负责人的最新消息。")
        lines.append("记住: 如果需求已经足够明确, 在回复末尾输出 <<<DELEGATE>>> 任务拆解JSON。")

        return "\n".join(lines)

    def _parse_delegation(self, reply: str) -> dict | None:
        """
        从回复中解析 <<<DELEGATE>>> ... <<<END>>> 块

        格式:
        <<<DELEGATE>>>
        {"tasks": [{"role": "frontend_dev", "description": "..."}, ...]}
        <<<END>>>
        """
        pattern = r'<<<DELEGATE>>>\s*\n?(.*?)\n?\s*<<<END>>>'
        match = re.search(pattern, reply, re.DOTALL)

        if not match:
            return None

        json_str = match.group(1).strip()

        # 尝试提取JSON对象 (可能被markdown代码块包裹)
        json_match = re.search(r'\{[\s\S]*"tasks"[\s\S]*\}', json_str)
        if json_match:
            json_str = json_match.group(0)

        try:
            delegation = json.loads(json_str)
            if "tasks" in delegation and isinstance(delegation["tasks"], list):
                # 验证每个任务
                for task in delegation["tasks"]:
                    if "role" not in task or "description" not in task:
                        return None
                return delegation
        except json.JSONDecodeError:
            pass

        return None

    def _clean_reply(self, reply: str) -> str:
        """移除回复中的 <<<DELEGATE>>> JSON块"""
        pattern = r'<<<DELEGATE>>>.*?<<<END>>>'
        cleaned = re.sub(pattern, '', reply, flags=re.DOTALL).strip()
        return cleaned

    def reset(self):
        """重置对话历史"""
        self.history = []

    def get_history(self) -> list[dict]:
        return self.history


# 全局单例
manager_chat = ManagerChat()
