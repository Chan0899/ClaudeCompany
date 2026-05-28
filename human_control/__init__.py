"""
human_control - 人类管控层

模块9: 六层架构-第一层
  - approval.py: 审批/驳回/启停/告警
"""
from human_control.approval import HumanApproval, human_approval

__all__ = ["HumanApproval", "human_approval"]
