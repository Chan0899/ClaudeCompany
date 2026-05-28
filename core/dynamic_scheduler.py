"""
AI动态统筹调度层 — 六层架构中的第3-4层

模块7: 优化原有调度逻辑, 支持智能分配、负载感知、自动重试

六层职责:
  第3层(SchedulingInfoProvider): 能力匹配 & 校验 Claude 的派活决定
  第4层(ExecutionController):   任务排序、负载控制、自动重试

架构:
  SchedulingInfoProvider  — 无状态只读查询 (角色能力、历史指标、团队记忆)
  ExecutionController     — 有状态执行控制 (负载、重试、反馈缓冲区)
  DynamicScheduler        — 门面, 保持向后兼容
"""
import os
import json
import time
import threading
from typing import Optional


# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ============================================================
# 第3层: 能力匹配 & 信息查询 (无状态只读)
# ============================================================

class SchedulingInfoProvider:
    """
    只读信息服务, 为管理AI和任务执行提供上下文。

    职责:
      - 构建团队能力矩阵 (角色、工具、目标)
      - 查询历史任务绩效指标
      - 优化任务排序 (基于依赖和历史耗时)
      - 构建任务执行上下文 (角色记忆、相似历史任务)
    """

    def optimize_order(self, tasks: list[dict]) -> list[dict]:
        """
        优化任务执行顺序

        规则:
          1. 无依赖的任务优先 → Phase 1
          2. 有依赖的任务 → Phase 2 (等依赖满足)
          3. 同 Phase 内按历史平均耗时升序 (快的先跑)
        """
        phase1 = [t for t in tasks if not t.get("depends_on")]
        phase2 = [t for t in tasks if t.get("depends_on")]

        role_timing = self.get_role_avg_timing()
        phase1.sort(key=lambda t: role_timing.get(t.get("role", ""), 999))
        phase2.sort(key=lambda t: role_timing.get(t.get("role", ""), 999))

        result = phase1 + phase2
        if not result and tasks:
            result = sorted(tasks, key=lambda t: len(t.get("depends_on", [])))

        return result

    def get_role_avg_timing(self) -> dict[str, float]:
        """从 data_store 获取各角色历史平均耗时"""
        try:
            from core.data_store import data_store
            metrics = data_store.query_task_metrics(recent_days=30)
            return {m["role"]: m["avg_seconds"] for m in metrics}
        except Exception:
            return {}

    def build_scheduling_context(self) -> str:
        """
        构建调度上下文, 注入到管理AI的 prompt 中

        包含: 各角色能力、工具清单、历史表现、团队记忆摘要
        """
        parts = []

        # 1. 角色能力矩阵
        try:
            from crew_adapter.agent_factory import agent_factory
            parts.append("【团队成员能力矩阵】")
            for rid in agent_factory.role_ids:
                cfg = agent_factory.get_agent_config(rid)
                if cfg:
                    tools = [t["name"] for t in cfg.get("tools", [])]
                    parts.append(
                        f"- {cfg['name']} ({rid}): "
                        f"擅长: {cfg['goal'][:80]}, "
                        f"工具: {', '.join(tools)}"
                    )
        except Exception:
            pass

        # 2. 历史任务绩效
        try:
            from core.data_store import data_store
            metrics = data_store.query_task_metrics(recent_days=7)
            if metrics:
                parts.append("\n【团队近期绩效 (近7天)】")
                for m in metrics:
                    parts.append(
                        f"- {m['role']}: {m['task_count']}个任务, "
                        f"完成{m['completed']}个, 平均{m['avg_seconds']}秒"
                    )
        except Exception:
            pass

        # 3. 团队共享记忆摘要
        try:
            from core.memory_manager import TeamMemory
            tm = TeamMemory()
            summary = tm.load_summary(max_chars=1000)
            if summary.strip():
                parts.append(f"\n【团队共享规范】\n{summary}")
        except Exception:
            pass

        # 4. 负载状态
        try:
            from core.dynamic_scheduler import scheduler
            active = scheduler.active_roles
            if active:
                parts.append("\n【当前各角色负载】")
                for rid, count in active.items():
                    parts.append(f"- {rid}: {count}个活跃任务")
        except Exception:
            pass

        return "\n".join(parts) if parts else ""

    def build_task_context(self, role_id: str, task_description: str) -> str:
        """
        为具体任务构建执行上下文

        注入: 角色长期记忆、相关项目经验、工具推荐
        """
        parts = []

        # 角色长期记忆
        try:
            from core.memory_manager import get_memory_manager
            mm = get_memory_manager(role_id)
            ctx = mm.load_context()
            if ctx:
                parts.append(ctx)
        except Exception:
            pass

        # 历史相似任务
        try:
            from core.data_store import data_store
            kw = task_description[:20]
            memories = data_store.query_memories(keyword=kw, role_id=role_id, limit=3)
            if memories:
                parts.append("\n【相关历史经验 (来自SQLite索引)】")
                for m in memories:
                    parts.append(f"- [{m['memory_type']}] {m['title']}: {m['content_preview'][:100]}")
        except Exception:
            pass

        return "\n".join(parts)

    def get_role_capabilities(self) -> dict:
        """返回角色能力矩阵字典, 供 validate_delegation 使用"""
        try:
            from crew_adapter.agent_factory import agent_factory
            caps = {}
            for rid in agent_factory.role_ids:
                cfg = agent_factory.get_agent_config(rid)
                if cfg:
                    caps[rid] = {
                        "name": cfg.get("name", rid),
                        "goal": cfg.get("goal", ""),
                        "tools": [t["name"] for t in cfg.get("tools", [])],
                    }
            return caps
        except Exception:
            return {}


# ============================================================
# 第4层: 执行控制 (有状态, 含锁)
# ============================================================

class ExecutionController:
    """
    有状态执行控制: 负载管理、重试逻辑、反馈缓冲。

    职责:
      - 角色负载控制 (每个角色最多1个并发任务)
      - 自动重试 (失败任务最多重试2次)
      - 反馈缓冲区 (执行事件回流到管理AI对话)
    """

    def __init__(self):
        self._active_roles: dict[str, int] = {}
        self._retry_counts: dict[str, int] = {}
        self._max_retries = 2
        self._max_concurrent_per_role = 1
        self._feedback_buffer: list[dict] = []
        self._lock = threading.Lock()

    # --- 负载控制 ---

    def can_launch(self, role_id: str) -> bool:
        with self._lock:
            current = self._active_roles.get(role_id, 0)
            return current < self._max_concurrent_per_role

    def mark_started(self, role_id: str):
        with self._lock:
            self._active_roles[role_id] = self._active_roles.get(role_id, 0) + 1

    def mark_finished(self, role_id: str):
        with self._lock:
            count = self._active_roles.get(role_id, 0)
            if count > 0:
                self._active_roles[role_id] = count - 1

    @property
    def active_roles(self) -> dict[str, int]:
        with self._lock:
            return dict(self._active_roles)

    # --- 自动重试 ---

    def should_retry(self, task_id: str) -> bool:
        with self._lock:
            count = self._retry_counts.get(task_id, 0)
            return count < self._max_retries

    def record_retry(self, task_id: str) -> int:
        with self._lock:
            count = self._retry_counts.get(task_id, 0) + 1
            self._retry_counts[task_id] = count
            return count

    def get_retry_count(self, task_id: str) -> int:
        with self._lock:
            return self._retry_counts.get(task_id, 0)

    def get_retry_context(self, task_id: str, last_error: str = "") -> str:
        count = self._retry_counts.get(task_id, 0)
        return (
            f"\n【重试上下文 - 第 {count + 1} 次尝试】\n"
            f"上次执行失败, 错误信息: {last_error[:300]}\n"
            f"请基于错误信息调整方案, 避免重复相同错误。\n"
        )

    # --- 反馈缓冲区 (新增) ---

    def add_feedback(self, event_type: str, data: dict):
        """线程安全写入反馈缓冲区, 上限50条"""
        with self._lock:
            self._feedback_buffer.append({
                "type": event_type,
                "data": data,
                "timestamp": time.time()
            })
            if len(self._feedback_buffer) > 50:
                self._feedback_buffer = self._feedback_buffer[-50:]

    def drain_feedback(self) -> list[dict]:
        """线程安全取出并清空所有反馈"""
        with self._lock:
            items = self._feedback_buffer[:]
            self._feedback_buffer.clear()
            return items

    @property
    def has_pending_feedback(self) -> bool:
        """是否有未消费的反馈"""
        with self._lock:
            return len(self._feedback_buffer) > 0


# ============================================================
# 门面: 保持向后兼容
# ============================================================

class DynamicScheduler:
    """
    调度器门面, 保持所有原有调用点兼容。

    新代码建议直接访问 scheduler.info / scheduler.executor。
    """

    def __init__(self):
        self.info = SchedulingInfoProvider()
        self.executor = ExecutionController()

    # --- 委托给 self.info (第3层: 只读查询) ---

    def optimize_order(self, tasks: list[dict]) -> list[dict]:
        return self.info.optimize_order(tasks)

    def build_scheduling_context(self) -> str:
        return self.info.build_scheduling_context()

    def build_task_context(self, role_id: str, task_description: str) -> str:
        return self.info.build_task_context(role_id, task_description)

    def _get_role_avg_timing(self) -> dict[str, float]:
        return self.info.get_role_avg_timing()

    def get_role_capabilities(self) -> dict:
        return self.info.get_role_capabilities()

    # --- 委托给 self.executor (第4层: 有状态执行) ---

    @property
    def active_roles(self) -> dict[str, int]:
        return self.executor.active_roles

    @property
    def has_pending_feedback(self) -> bool:
        return self.executor.has_pending_feedback

    def can_launch(self, role_id: str) -> bool:
        return self.executor.can_launch(role_id)

    def mark_started(self, role_id: str):
        self.executor.mark_started(role_id)

    def mark_finished(self, role_id: str):
        self.executor.mark_finished(role_id)

    def should_retry(self, task_id: str) -> bool:
        return self.executor.should_retry(task_id)

    def record_retry(self, task_id: str) -> int:
        return self.executor.record_retry(task_id)

    def get_retry_count(self, task_id: str) -> int:
        return self.executor.get_retry_count(task_id)

    def get_retry_context(self, task_id: str, last_error: str = "") -> str:
        return self.executor.get_retry_context(task_id, last_error)

    def add_feedback(self, event_type: str, data: dict):
        self.executor.add_feedback(event_type, data)

    def drain_feedback(self) -> list[dict]:
        return self.executor.drain_feedback()

    # --- 第3层核心: 校验 Claude 的派活决定 ---

    def validate_delegation(self, delegation: dict) -> dict:
        """
        校验管理AI的任务拆解, 确保角色存在、空闲、依赖可满足。

        输入: {"tasks": [{"role": "frontend_dev", "description": "..."}, ...]}
        输出: {
            "valid": True/False,
            "issues": [{"task_index": 0, "type": "...", "message": "..."}],
            "valid_tasks": [...],
            "blocked_tasks": [...],
        }
        """
        tasks = delegation.get("tasks", [])
        issues = []
        valid_tasks = []
        blocked_tasks = []

        # 获取已注册角色
        capabilities = self.info.get_role_capabilities()
        known_roles = set(capabilities.keys())
        # 所有在同批次中出现的角色 (用于依赖校验)
        all_assigned_roles = {t.get("role", "") for t in tasks}

        for i, task in enumerate(tasks):
            role = task.get("role", "")
            desc = task.get("description", "")
            deps = task.get("depends_on", [])

            # 校验1: 角色是否存在
            if role not in known_roles:
                issues.append({
                    "task_index": i,
                    "type": "role_unknown",
                    "message": f"未知角色 '{role}', 可用角色: {', '.join(sorted(known_roles))}"
                })
                blocked_tasks.append({**task, "block_reason": f"未知角色: {role}"})
                continue

            # 校验2: 角色是否空闲
            if not self.executor.can_launch(role):
                issues.append({
                    "task_index": i,
                    "type": "role_overloaded",
                    "message": f"{capabilities.get(role, {}).get('name', role)} 当前繁忙, 任务「{desc[:30]}」已加入等待队列"
                })
                blocked_tasks.append({**task, "block_reason": f"角色 {role} 负载已满"})
                continue

            # 校验3: 依赖是否可满足
            unsatisfied = []
            for dep_role in deps:
                if dep_role not in known_roles and dep_role not in all_assigned_roles:
                    unsatisfied.append(dep_role)
            if unsatisfied:
                issues.append({
                    "task_index": i,
                    "type": "dependency_unknown",
                    "message": f"任务「{desc[:30]}」依赖未知角色: {', '.join(unsatisfied)}"
                })
                # 依赖未知不算阻塞, 只警告

            # 校验4: 任务描述是否足够具体
            if len(desc.strip()) < 10:
                issues.append({
                    "task_index": i,
                    "type": "description_too_short",
                    "message": f"任务「{desc}」描述过于简短 (需 ≥ 10字), 可能导致执行质量不佳"
                })
                # 不阻塞, 只警告

            valid_tasks.append(task)

        return {
            "valid": len(issues) == 0 or all(
                i["type"] in ("dependency_unknown", "description_too_short") for i in issues
            ),
            "issues": issues,
            "valid_tasks": valid_tasks,
            "blocked_tasks": blocked_tasks,
        }


# ============================================================
# 全局单例
# ============================================================
scheduler = DynamicScheduler()
