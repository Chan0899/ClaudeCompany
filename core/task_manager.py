"""
任务管理器 - 任务生命周期管理 (创建、拆解、分配、追踪、审批)
"""
import uuid
import time
import threading
from typing import Optional
from core.event_bus import event_bus


class Task:
    """单个任务/子任务"""

    def __init__(self, description: str, assigned_role: str = None, parent_id: str = None,
                 depends_on: list[str] = None):
        self.id = str(uuid.uuid4())[:8]
        self.description = description
        self.assigned_role = assigned_role      # 分配的角色ID
        self.parent_id = parent_id               # 父任务ID (子任务)
        self.depends_on = depends_on or []       # 依赖的角色列表 (这些角色完成后再启动)
        self.status = "pending"                  # pending|assigned|in_progress|done|approved|rejected
        self.result = None                       # 执行结果
        self.created_at = time.time()
        self.completed_at = None
        self.reject_reason = None                # 驳回原因


class TaskManager:
    """全局任务管理器"""

    def __init__(self):
        self.tasks: dict[str, Task] = {}         # 所有任务
        self.subtasks: list[Task] = []           # 当前活跃的子任务
        self._lock = threading.Lock()
        self._completion_callbacks = []

    def create_task(self, description: str) -> Task:
        """创建顶层任务 (来自人类需求)"""
        task = Task(description=description)
        with self._lock:
            self.tasks[task.id] = task
        event_bus.publish("task_created", {
            "task_id": task.id,
            "description": description,
            "status": task.status
        })
        return task

    def create_subtask(self, description: str, assigned_role: str, parent_id: str,
                        depends_on: list[str] = None) -> Task:
        """创建子任务 (管理AI拆解后), 可指定依赖"""
        subtask = Task(description=description, assigned_role=assigned_role,
                       parent_id=parent_id, depends_on=depends_on)
        with self._lock:
            self.tasks[subtask.id] = subtask
            self.subtasks.append(subtask)
            subtask.status = "assigned"

        event_bus.publish("subtask_created", {
            "task_id": subtask.id,
            "parent_id": parent_id,
            "description": description,
            "assigned_role": assigned_role,
            "status": subtask.status
        })
        return subtask

    def update_status(self, task_id: str, status: str, result: dict = None):
        """更新任务状态"""
        with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return
            task.status = status
            if result:
                task.result = result
            if status == "done":
                task.completed_at = time.time()

        event_bus.publish("task_status", {
            "task_id": task_id,
            "status": status,
            "result": result
        })

        # 检查所有子任务是否完成
        if status == "done":
            self._check_parent_completion(task)

    def _check_parent_completion(self, completed_subtask: Task):
        """检查父任务的所有子任务是否都完成"""
        parent_id = completed_subtask.parent_id
        if not parent_id:
            return

        with self._lock:
            siblings = [t for t in self.subtasks if t.parent_id == parent_id]
            all_done = all(t.status == "done" for t in siblings)

        if all_done and siblings:
            parent = self.tasks.get(parent_id)
            if parent:
                # 收集所有子任务结果
                results = {}
                for s in siblings:
                    if s.result:
                        role = s.assigned_role or "unknown"
                        results[role] = s.result

                self.update_status(parent_id, "pending_approval", results)
                event_bus.publish("ready_for_approval", {
                    "task_id": parent_id,
                    "description": parent.description,
                    "subtasks_results": results
                })

    def approve_task(self, task_id: str):
        """人类审批通过"""
        self.update_status(task_id, "approved")
        event_bus.publish("task_approved", {
            "task_id": task_id
        })

    def reject_task(self, task_id: str, reason: str = ""):
        """人类驳回任务"""
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                task.reject_reason = reason
        self.update_status(task_id, "rejected")
        event_bus.publish("task_rejected", {
            "task_id": task_id,
            "reason": reason
        })

    def get_all_tasks(self) -> list[dict]:
        """获取所有任务列表"""
        with self._lock:
            result = []
            for t in self.tasks.values():
                result.append({
                    "id": t.id,
                    "description": t.description,
                    "assigned_role": t.assigned_role,
                    "parent_id": t.parent_id,
                    "depends_on": t.depends_on,
                    "status": t.status,
                    "result": t.result,
                    "reject_reason": t.reject_reason,
                    "created_at": t.created_at,
                    "completed_at": t.completed_at
                })
            # 按创建时间倒序
            result.sort(key=lambda x: x["created_at"], reverse=True)
            return result


# 全局单例
task_manager = TaskManager()
