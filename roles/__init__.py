"""
roles - 多员工角色包

模块2: 目录重构 + 多员工文件体系搭建

每个员工独立目录, 包含:
  - role_config.yaml: 角色配置
  - claude.md: 人设手册
  - memory/: 个人记忆 (short_term.json + long_term.md)
  - logs/: 个人日志

向后兼容: 保留原有 simulated 模式的类导入路径
"""
# 向后兼容导入: app.py 中的原有 import 路径保持不变
from roles.frontend_dev.simulated import FrontendDevAI  # noqa: F401
from roles.backend_dev.simulated import BackendDevAI    # noqa: F401
from roles.tester.simulated import TesterAI             # noqa: F401
