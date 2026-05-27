"""
执行AI基类 - 模拟AI工作流程 (思考→编码→完成)
"""
import threading
import time
import random
import uuid
from abc import ABC, abstractmethod
from core.event_bus import event_bus
from core.workspace import workspace
from config import AI_THINKING_MIN, AI_THINKING_MAX, AI_CODING_MIN, AI_CODING_MAX


class ExecutorAI(ABC):
    """执行AI基类, 每个实例在独立线程中运行"""

    def __init__(self, ai_id: str, name: str, role: str):
        self.ai_id = ai_id
        self.name = name
        self.role = role
        self.status = "idle"          # idle | thinking | coding | done | error
        self.current_task = None      # 当前正在处理的任务
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def _log(self, message: str):
        """发布日志到事件总线"""
        print(f"[{self.name}] {message}")
        event_bus.publish("log", {
            "ai_id": self.ai_id,
            "ai_name": self.name,
            "message": message
        })

    def _set_status(self, status: str):
        """更新状态并推送"""
        self.status = status
        event_bus.publish("ai_status", {
            "ai_id": self.ai_id,
            "ai_name": self.name,
            "status": status,
            "current_task": self.current_task
        })

    def execute(self, task: dict):
        """在独立线程中执行任务"""
        self.current_task = task
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, args=(task,), daemon=True)
        self._thread.start()

    def _run(self, task: dict):
        """AI工作流程: 思考 → 编码 → 完成"""
        task_id = task.get("id", "unknown")
        task_desc = task.get("description", "")

        try:
            # 阶段1: 思考分析
            self._set_status("thinking")
            self._log(f"收到任务 [{task_id}]: {task_desc}")
            think_time = random.uniform(AI_THINKING_MIN, AI_THINKING_MAX)
            self._log(f"正在分析需求... (预计{think_time:.1f}秒)")
            time.sleep(think_time)
            self._log(f"需求分析完成, 准备开始编码")

            # 阶段2: 编码实现
            self._set_status("coding")
            self._log(f"开始编写代码...")
            code_time = random.uniform(AI_CODING_MIN, AI_CODING_MAX)
            time.sleep(code_time)

            # 子类实现具体编码逻辑
            result = self.do_work(task)

            # 阶段3: 完成
            self._set_status("done")
            self._log(f"任务完成! 已生成: {result.get('files', [])}")

            # 推送任务完成事件
            event_bus.publish("subtask_done", {
                "ai_id": self.ai_id,
                "task_id": task_id,
                "result": result
            })

        except Exception as e:
            self._set_status("error")
            self._log(f"执行出错: {str(e)}")

    @abstractmethod
    def do_work(self, task: dict) -> dict:
        """子类实现: 执行具体编码工作, 返回结果"""
        pass

    def stop(self):
        """停止AI"""
        self._stop_event.set()
        self._set_status("idle")
        self.current_task = None
