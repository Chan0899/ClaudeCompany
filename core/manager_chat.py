"""
管理AI对话引擎 — 六层流水线中的第1-3层

六层架构:
  第1层 (预处理):        反馈注入、消息清洗、历史管理
  第2层 (意图理解):      Claude LLM (MANAGER_SYSTEM_PROMPT), 聊天/追问/派活
  第3层 (校验匹配):      scheduler.validate_delegation(), 角色/负载/依赖校验
  第4层 (任务排序):      scheduler.optimize_order() — 由 _spawn_workers 触发
  第5层 (人类确认):      quality_checker + 审批流程 — 由 API 路由触发
  第6层 (状态分发):      event_bus → worker_done → feedback 回流

流程:
  1. 人类发消息 → 第1层预处理 + 注入上轮反馈
  2. 第2层 Claude (仅 team_memory, 不注入调度上下文)
  3. Claude 回复 → 第3层校验 <<<DELEGATE>>> 是否合法
  4. 校验通过的任务交给 app.py 派发
"""
import json
import re
import os
from config import MANAGER_SYSTEM_PROMPT
from core.llm_client import llm_client
from core.memory_manager import TeamMemory


class ManagerChat:
    """管理AI对话管理: 维护历史, 调用Claude, 解析拆解, 校验派活"""

    def __init__(self):
        self.history: list[dict] = []
        self.max_history = 20

    # ================================================================
    # 第1层: 预处理
    # ================================================================

    def chat(self, message: str) -> dict:
        """
        六层流水线主入口。

        返回格式:
        {
            "reply": "管理AI的回复文本 (含校验提示)",
            "delegation": None | {"tasks": [...]},
            "error": None | "错误信息"
        }
        """
        # ---------- 第1层: 预处理 ----------

        # 1a. 注入上轮执行反馈 (feedback 回流)
        from core.dynamic_scheduler import scheduler
        feedbacks = scheduler.drain_feedback()
        for fb in feedbacks:
            formatted = self._format_feedback(fb)
            self.history.append({"role": "system", "content": formatted})

        # 1b. 记录人类消息
        self.history.append({"role": "human", "content": message})

        # ---------- 第2层: 意图理解 (Claude, 不注入调度上下文) ----------

        prompt = self._build_prompt()
        team_memory = TeamMemory()
        memory_context = team_memory.load_summary(max_chars=1500)

        workspace_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "workspace"
        )
        result = llm_client.chat(
            prompt=prompt,
            system_prompt=MANAGER_SYSTEM_PROMPT,
            allowed_tools=["Read", "Glob", "Grep"],
            cwd=workspace_dir,
            timeout=180,
            memory_context=memory_context  # 只传团队记忆, 不传调度上下文
        )

        if not result["success"]:
            return {
                "reply": result.get("reply", f"错误: {result['error']}"),
                "delegation": None,
                "error": result["error"]
            }

        reply = result["reply"]

        # ---------- 第3层: 校验 Claude 的派活决定 ----------

        delegation = self._parse_delegation(reply)
        clean_reply = self._clean_reply(reply)

        if delegation:
            validation = scheduler.validate_delegation(delegation)

            # 追加校验提示到回复
            for issue in validation["issues"]:
                suffix = "\n\n⚠ " if issue["type"] in (
                    "role_unknown", "role_overloaded"
                ) else "\n\nℹ "
                clean_reply += suffix + issue["message"]

            # 被阻塞的任务写 feedback
            for bt in validation["blocked_tasks"]:
                scheduler.add_feedback("task_blocked", {
                    "role": bt.get("role", ""),
                    "description": bt.get("description", ""),
                    "block_reason": bt.get("block_reason", ""),
                })

            # 只保留校验通过的任务
            delegation["tasks"] = validation["valid_tasks"]
            if not delegation["tasks"]:
                delegation = None  # 全部阻塞, 不触发派发

        # 记录管理AI回复
        self.history.append({"role": "manager", "content": clean_reply})
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

        return {
            "reply": clean_reply,
            "delegation": delegation,
            "error": None
        }

    # ================================================================
    # 第1层辅助: 反馈格式化
    # ================================================================

    def _format_feedback(self, fb: dict) -> str:
        """将原始反馈 dict 格式化为管理AI可读的系统消息"""
        etype = fb["type"]
        data = fb["data"]
        role = data.get("role", "未知")
        desc = data.get("description", "")[:60]

        templates = {
            "task_blocked": (
                f"【任务调度 - 阻塞】角色「{role}」负载已满, "
                f"任务「{desc}」已加入等待队列。原因: {data.get('block_reason', '未知')}"
            ),
            "task_retrying": (
                f"【任务执行 - 重试】角色「{role}」执行「{desc}」失败, "
                f"正在自动重试 (第 {data.get('retry_count', '?')} 次)。"
                f"错误: {data.get('error', '')[:150]}"
            ),
            "task_failed": (
                f"【任务执行 - 失败】角色「{role}」执行「{desc}」最终失败, "
                f"已重试 {data.get('retry_count', '?')} 次。请考虑重新分配或调整方案。"
            ),
            "task_done": (
                f"【任务执行 - 完成】角色「{role}」已完成「{desc}」。"
                + (f" 产出文件: {data.get('files', [])}" if data.get("files") else "")
            ),
            "dependency_blocked": (
                f"【任务调度 - 依赖等待】角色「{role}」的任务「{desc}」已排队, "
                f"等待前置角色完成: {data.get('depends_on', [])}"
            ),
            "dependency_resolved": (
                f"【任务调度 - 依赖就绪】角色「{role}」的任务「{desc}」"
                f"等待 {data.get('depends_on', [])} 完成后已启动。"
            ),
        }
        return templates.get(etype, f"【执行反馈 - {etype}】{data}")

    # ================================================================
    # 第2层辅助: 构建 prompt
    # ================================================================

    def _build_prompt(self) -> str:
        """构建包含对话历史的提示词, 支持 system 角色消息"""
        lines = []
        lines.append("以下是对话历史 (你是管理AI, 对方是人类负责人):\n")

        for msg in self.history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "human":
                lines.append(f"【人类负责人】: {content}")
            elif role == "system":
                lines.append(f"【系统通知 - 任务执行反馈】: {content}")
            else:
                lines.append(f"【你(管理AI)】: {content}")

        lines.append("")
        lines.append("请根据以上对话, 回复人类负责人的最新消息。")
        lines.append("记住: 如果需求已经足够明确, 在回复末尾输出 <<<DELEGATE>>> 任务拆解JSON。")

        return "\n".join(lines)

    # ================================================================
    # 第3层辅助: 解析 & 清洗
    # ================================================================

    def _parse_delegation(self, reply: str) -> dict | None:
        """
        从回复中解析 <<<DELEGATE>>> ... <<<END>>> 块

        格式:
        <<<DELEGATE>>>
        {"tasks": [{"role": "frontend_dev", "description": "..."}, ...],
         "depends_on": ["other_role"]}  # 可选
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

    # ================================================================
    # 工具方法
    # ================================================================

    def reset(self):
        """重置对话历史"""
        self.history = []

    def get_history(self) -> list[dict]:
        return self.history


# 全局单例
manager_chat = ManagerChat()
