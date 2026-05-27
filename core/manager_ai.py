"""
管理AI - 中枢协调层: 接收需求 → 智能拆解 → 分配执行AI → 监控进度 → 提交审批

支持两种模式:
  - simulated: Python线程模拟AI工作
  - claude:    启动真实Claude终端窗口
"""
import threading
import time
import random
from config import AI_MODE
from core.event_bus import event_bus
from core.task_manager import task_manager


class ManagerAI:
    """管理AI: 团队大脑, 负责任务编排和流程管控"""

    def __init__(self, executor_pool: dict):
        """
        executor_pool: {"frontend_dev": FrontendDevAI实例, ...}
        """
        self.ai_id = "manager"
        self.name = "管理AI"
        self.role = "团队管理者"
        self.status = "idle"
        self.executor_pool = executor_pool
        self._processing = False

    def _log(self, message: str):
        print(f"[{self.name}] {message}")
        event_bus.publish("log", {
            "ai_id": self.ai_id,
            "ai_name": self.name,
            "message": message
        })

    def _set_status(self, status: str):
        self.status = status
        event_bus.publish("ai_status", {
            "ai_id": self.ai_id,
            "ai_name": self.name,
            "status": status,
            "current_task": None
        })

    def handle_requirement(self, requirement: str):
        """
        处理人类提交的需求:
        1. 分析理解需求
        2. 拆解为子任务
        3. 分配给执行AI
        4. 进入监控模式
        """
        if self._processing:
            self._log("当前有任务正在处理中, 请稍后再提交")
            return None

        self._processing = True
        thread = threading.Thread(target=self._process, args=(requirement,), daemon=True)
        thread.start()
        return thread

    def _process(self, requirement: str):
        """管理AI的处理流程 (在独立线程中运行)"""
        try:
            # 步骤1: 创建顶层任务
            self._set_status("thinking")
            self._log(f"收到人类需求: 「{requirement}」")
            time.sleep(0.5)

            # 步骤2: 智能拆解
            self._log("正在分析需求, 拆解子任务...")
            time.sleep(1.5)

            parent_task = task_manager.create_task(requirement)
            subtasks = self._decompose(requirement, parent_task.id)

            self._log(f"需求拆解完成 → {len(subtasks)}个子任务:")
            for st in subtasks:
                role_name = st["role_name"]
                desc = st["description"]
                self._log(f"  • [{role_name}] {desc}")

            # 步骤3: 分配给执行AI
            self._set_status("assigning")

            if AI_MODE == "claude":
                self._launch_claude_terminals(requirement, subtasks, parent_task.id)
            else:
                self._assign_to_simulated(subtasks, parent_task.id, requirement)

            # 步骤4: 监控模式 - 等待所有子任务完成
            self._set_status("monitoring")
            self._log("所有子任务已分配, 进入监控模式...")

            if AI_MODE == "claude":
                # Claude模式: 轮询检测工作区文件变化
                self._monitor_claude_progress(requirement, subtasks, parent_task.id)
            else:
                self._log("等待执行AI完成工作...")

        except Exception as e:
            self._set_status("error")
            self._log(f"处理出错: {str(e)}")
            self._processing = False

    def _decompose(self, requirement: str, parent_id: str) -> list[dict]:
        """
        需求拆解逻辑 (Demo版: 基于关键词简单拆解)
        实际可替换为真正的LLM调用
        """
        req_lower = requirement.lower()
        subtasks = []

        # 前端相关
        if any(kw in req_lower for kw in ["页面", "界面", "ui", "前端", "登录", "表单", "按钮", "展示", "列表", "表格"]):
            subtasks.append({
                "role": "frontend_dev",
                "role_name": "前端开发AI",
                "description": f"开发前端页面: {requirement}"
            })

        # 后端相关
        if any(kw in req_lower for kw in ["api", "接口", "后端", "数据", "登录", "注册", "存储", "查询", "服务", "逻辑", "数据库"]):
            subtasks.append({
                "role": "backend_dev",
                "role_name": "后端开发AI",
                "description": f"开发后端接口: {requirement}"
            })

        # 如果都没有明确偏向, 默认创建前端+后端
        if not subtasks:
            subtasks.append({
                "role": "frontend_dev",
                "role_name": "前端开发AI",
                "description": f"开发前端页面: {requirement}"
            })
            subtasks.append({
                "role": "backend_dev",
                "role_name": "后端开发AI",
                "description": f"开发后端接口: {requirement}"
            })

        # 总是添加测试任务
        subtasks.append({
            "role": "tester",
            "role_name": "测试AI",
            "description": f"编写测试用例: {requirement}"
        })

        return subtasks

    def _assign_to_simulated(self, subtasks: list[dict], parent_id: str, requirement: str):
        """simulated模式: 将任务分配给Python模拟AI"""
        for st in subtasks:
            subtask = task_manager.create_subtask(
                description=st["description"],
                assigned_role=st["role"],
                parent_id=parent_id
            )
            self._log(f"分配任务 [{subtask.id}] → {st['role_name']} (模拟)")

            executor = self.executor_pool.get(st["role"])
            if executor:
                executor.execute({
                    "id": subtask.id,
                    "description": st["description"],
                    "feature": requirement,
                    "parent_id": parent_id
                })
            else:
                self._log(f"警告: 未找到角色 {st['role']} 的执行AI")

    def _launch_claude_terminals(self, requirement: str, subtasks: list[dict], parent_id: str):
        """claude模式: 为每个执行AI打开独立的Claude终端窗口"""
        from core.terminal_launcher import launch_claude_terminal

        # 角色ID → 工作区子目录映射
        role_dir_map = {
            "frontend_dev": "frontend",
            "backend_dev": "backend",
            "tester": "tests",
        }

        for st in subtasks:
            subtask = task_manager.create_subtask(
                description=st["description"],
                assigned_role=st["role"],
                parent_id=parent_id
            )
            self._log(f"分配任务 [{subtask.id}] → {st['role_name']} (Claude终端)")

            role_id = st["role"]
            workspace_subdir = role_dir_map.get(role_id, role_id)

            # 启动独立Claude终端窗口
            success = launch_claude_terminal(
                role_id=role_id,
                role_name=st["role_name"],
                workspace_subdir=workspace_subdir,
                task_description=st["description"],
                feature=requirement
            )

            if success:
                self._log(f"✓ 已为 {st['role_name']} 打开Claude终端窗口")
            else:
                self._log(f"✗ 启动 {st['role_name']} 的Claude终端失败")

    def _monitor_claude_progress(self, requirement: str, subtasks: list[dict], parent_id: str):
        """Claude模式监控: 轮询工作区, 检测每个角色的产出文件"""
        import os
        from config import WORKSPACE_DIR
        from core.workspace import workspace

        role_dir_map = {
            "frontend_dev": "frontend",
            "backend_dev": "backend",
            "tester": "tests",
        }

        # 记录监控开始时的文件快照
        baseline = {}
        for st in subtasks:
            subdir = role_dir_map.get(st["role"], st["role"])
            role_dir = os.path.join(WORKSPACE_DIR, subdir)
            if os.path.exists(role_dir):
                # 过滤掉系统文件
                baseline[st["role"]] = set(
                    f for f in os.listdir(role_dir)
                    if not f.startswith("_") and not f.endswith(".tmp")
                )
            else:
                baseline[st["role"]] = set()

        self._log("开始监控Claude终端产出... (每5秒检查一次, 最长等待120秒)")

        max_wait = 120  # 最长等待120秒
        poll_interval = 5

        for _ in range(max_wait // poll_interval):
            time.sleep(poll_interval)
            all_done = True

            for st in subtasks:
                role_id = st["role"]
                subdir = role_dir_map.get(role_id, role_id)
                role_dir = os.path.join(WORKSPACE_DIR, subdir)

                current_files = set()
                if os.path.exists(role_dir):
                    current_files = set(
                        f for f in os.listdir(role_dir)
                        if not f.startswith("_") and not f.endswith(".tmp")
                    )

                new_files = current_files - baseline.get(role_id, set())

                if new_files:
                    self._log(f"✓ {st['role_name']} 已产出: {', '.join(new_files)}")

                    # 更新对应子任务状态
                    for tid, task in task_manager.tasks.items():
                        if (task.parent_id == parent_id and
                            task.assigned_role == role_id and
                            task.status != "done"):
                            task_manager.update_status(tid, "done", {
                                "files": [f"{subdir}/{f}" for f in new_files],
                                "role": role_id
                            })
                else:
                    all_done = False

            if all_done:
                self._log("所有Claude终端均已产出文件!")
                break
        else:
            self._log("监控超时, 部分Claude终端可能仍在工作中")
            # 标记已有产出的为完成
            for st in subtasks:
                role_id = st["role"]
                subdir = role_dir_map.get(role_id, role_id)
                role_dir = os.path.join(WORKSPACE_DIR, subdir)
                current_files = set()
                if os.path.exists(role_dir):
                    current_files = set(
                        f for f in os.listdir(role_dir)
                        if not f.startswith("_") and not f.endswith(".tmp")
                    )
                new_files = current_files - baseline.get(role_id, set())
                if new_files:
                    for tid, task in task_manager.tasks.items():
                        if (task.parent_id == parent_id and
                            task.assigned_role == role_id and
                            task.status != "done"):
                            task_manager.update_status(tid, "done", {
                                "files": [f"{subdir}/{f}" for f in new_files],
                                "role": role_id
                            })

        # 触发审批检查
        for tid, task in list(task_manager.tasks.items()):
            if task.parent_id == parent_id:
                task_manager._check_parent_completion(task)
                break

        self._processing = False

    def on_subtasks_all_done(self, task_id: str):
        """所有子任务完成后的回调"""
        self._log(f"任务 [{task_id}] 所有子任务已完成, 等待人类审批...")
        self._set_status("idle")
        self._processing = False
