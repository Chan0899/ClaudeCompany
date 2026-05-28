"""
crew_adapter - CrewAI 适配层

模块4: CrewAI适配层开发 (Agent工厂)

功能:
  - 读取 roles/<id>/role_config.yaml + claude.md
  - 动态创建标准 CrewAI Agent 实例
  - 自动绑定 tools/ 注册中心的工具
  - 零硬编码, 所有角色信息来自文件配置
"""
from crew_adapter.agent_factory import AgentFactory, agent_factory  # noqa: F401
