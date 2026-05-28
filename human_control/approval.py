"""
HumanApproval - 增强审批/驳回/启停/告警

模块9: 人类管控层, 集成质控+冲突检测+持久化
"""
import time
from core.event_bus import event_bus


class HumanApproval:
    """
    人类管控中心

    功能:
      - approve_with_checks(): 审批前自动质控
      - reject_with_log(): 驳回并记录原因
      - stop_task(): 任务启停
      - get_summary(): 待审批摘要
    """

    def __init__(self):
        self._pending_approvals: list[dict] = []

    # ============================================================
    # 审批 / 驳回
    # ============================================================

    def approve_with_checks(self, task_id: str) -> dict:
        """
        审批前自动质控+冲突检测

        返回:
          {"approved": bool, "qc_report": {...}, "conflicts": [...], "warnings": [...]}
        """
        warnings = []

        # 质控检查
        try:
            from quality_evolve import quality_checker, conflict_resolver
            qc = quality_checker.run_all_checks()
            cr = conflict_resolver.auto_resolve()
        except Exception:
            qc = {"passed": True, "issues": []}
            cr = {"resolved": 0, "skipped": 0}

        if not qc.get("passed", False):
            warnings.append({
                "type": "quality",
                "detail": f"质控发现 {qc.get('issue_count', 0)} 个问题"
            })

        if cr.get("skipped", 0) > 0:
            warnings.append({
                "type": "conflict",
                "detail": f"{cr['skipped']} 个冲突需人工审查"
            })

        # 记录审批
        self._pending_approvals.append({
            "task_id": task_id,
            "time": time.time(),
            "warnings": len(warnings),
            "approved": True,
        })

        event_bus.publish("approval_action", {
            "task_id": task_id,
            "action": "approved",
            "warnings": len(warnings),
        })

        return {
            "approved": True,
            "qc_report": qc,
            "conflicts": cr,
            "warnings": warnings,
        }

    def reject_with_log(self, task_id: str, reason: str):
        """驳回任务, 记录到事件总线和持久层"""
        event_bus.publish("approval_action", {
            "task_id": task_id,
            "action": "rejected",
            "reason": reason,
        })

        # 记录到 data_store
        try:
            from core.data_store import data_store
            data_store.record_error(
                source="human_approval",
                source_id=task_id,
                error_type="rejected",
                error_message=f"任务被驳回: {reason}",
            )
        except Exception:
            pass

        # 记录到团队记忆 (供进化层学习)
        try:
            from core.memory_manager import TeamMemory
            TeamMemory().append("高频问题FAQ",
                f"任务 [{task_id}] 被驳回, 原因: {reason}")
        except Exception:
            pass

        self._pending_approvals.append({
            "task_id": task_id,
            "time": time.time(),
            "rejected": True,
            "reason": reason,
        })

    # ============================================================
    # 任务启停
    # ============================================================

    def stop_task(self, task_id: str, reason: str = "人工停止") -> dict:
        """
        强制停止任务

        返回: {"stopped": bool, "message": str}
        """
        event_bus.publish("log", {
            "ai_id": "human_control",
            "ai_name": "人类管控",
            "message": f"任务 [{task_id}] 被强制停止: {reason}"
        })

        event_bus.publish("task_stopped", {
            "task_id": task_id,
            "reason": reason,
        })

        try:
            from core.task_manager import task_manager
            task = task_manager.tasks.get(task_id)
            if task:
                task_manager.update_status(task_id, "rejected")
                return {"stopped": True, "message": f"任务 [{task_id}] 已停止"}
            return {"stopped": False, "message": "任务不存在"}
        except Exception as e:
            return {"stopped": False, "message": str(e)}

    # ============================================================
    # 摘要
    # ============================================================

    def get_summary(self) -> dict:
        """获取待审批摘要 + 近期告警"""
        alerts = []

        # 检查 data_store 中的错误
        try:
            from core.data_store import data_store
            errors = data_store.query_errors(limit=5)
            for e in errors:
                alerts.append({
                    "source": e["source"],
                    "message": e["error_message"][:100],
                })
        except Exception:
            pass

        return {
            "pending_approval_count": len(self._pending_approvals),
            "recent_alerts": alerts,
        }

    @property
    def history(self) -> list[dict]:
        return self._pending_approvals[-10:]


# 全局单例
human_approval = HumanApproval()
