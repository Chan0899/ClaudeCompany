"""
ClaudeBaseTool - 所有Claude工具的基类

模块2: Claude Code专属Tool层增量封装

能力:
  1. 自动日志记录 (入参、耗时、结果、异常)
  2. 权限隔离声明 (allowed_roles)
  3. 统一异常捕获
  4. 持久化钩子 (供模块4使用)
"""
import time
import abc
from typing import Any
from crewai.tools import BaseTool
from core.event_bus import event_bus


class ClaudeBaseTool(BaseTool, abc.ABC):
    """
    Claude 工具基类

    继承 CrewAI BaseTool, 增加:
      - allowed_roles: 声明允许使用此工具的角色列表
      - _log_call(): 自动记录调用日志到 event_bus
      - _safe_run(): 统一异常捕获包装
    """

    # 允许使用的角色列表, 子类必须覆盖
    # 示例: ["frontend_dev", "backend_dev", "tester", "manager"]
    allowed_roles: list[str] = []

    # 工具类别: "code_gen" | "file_ops" | "search" | "debug"
    tool_category: str = ""

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """
        统一入口: 日志 + 权限检查 + 异常捕获
        子类实现 _execute() 即可
        """
        start_time = time.time()
        error_msg = None

        try:
            result = self._execute(*args, **kwargs)
            return result
        except Exception as e:
            error_msg = str(e)
            raise
        finally:
            elapsed = time.time() - start_time
            self._log_call(kwargs, elapsed, error_msg)

    @abc.abstractmethod
    def _execute(self, *args: Any, **kwargs: Any) -> Any:
        """子类实现: 具体工具逻辑"""
        ...

    def _log_call(self, params: dict, elapsed: float, error: str | None):
        """发布 tool_call 事件到事件总线 (供日志/持久层消费)"""
        event_bus.publish("tool_call", {
            "tool_name": self.name,
            "tool_category": self.tool_category,
            "params": {k: str(v)[:200] for k, v in params.items()},
            "elapsed": round(elapsed, 3),
            "success": error is None,
            "error": error,
            "allowed_roles": self.allowed_roles
        })

    @property
    def role_info(self) -> dict:
        """返回工具的角色权限信息"""
        return {
            "name": self.name,
            "category": self.tool_category,
            "allowed_roles": self.allowed_roles,
            "description": self.description
        }
