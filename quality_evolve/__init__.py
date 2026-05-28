"""
quality_evolve - 质控 & 冲突调解 & 自进化层

模块8: 六层架构-第五层
  - checker.py: 代码质量检查
  - conflict_resolver.py: 多员工冲突调解
  - evolver.py: 自主复盘与经验进化
"""
from quality_evolve.checker import QualityChecker, quality_checker
from quality_evolve.conflict_resolver import ConflictResolver, conflict_resolver
from quality_evolve.evolver import Evolver, evolver

__all__ = [
    "QualityChecker", "quality_checker",
    "ConflictResolver", "conflict_resolver",
    "Evolver", "evolver",
]
