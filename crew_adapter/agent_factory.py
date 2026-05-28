"""
Agent 工厂 - 文件化配置驱动的 CrewAI Agent 创建器

模块4: CrewAI适配层开发 (Agent工厂)

功能:
  1. 读取 roles/<id>/role_config.yaml 角色配置
  2. 读取 roles/<id>/claude.md 人设文件
  3. 从 tools/ 注册中心绑定专属工具
  4. 动态创建标准 CrewAI Agent 实例

原则: 零硬编码, 所有角色信息来自文件配置
"""
import os
import yaml
from crewai import Agent
from tools.registry import tool_registry


# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROLES_DIR = os.path.join(BASE_DIR, "roles")


class AgentFactory:
    """
    Agent 工厂 - 读取文件配置动态生成 CrewAI Agent

    数据流:
      roles/<id>/role_config.yaml → 角色元信息 + 工具绑定
      roles/<id>/claude.md       → Agent backstory (人设)
      tools/registry             → 工具实例

    用法:
      factory = AgentFactory()
      agent = factory.create_agent("frontend_dev")
      config = factory.get_agent_config("tester")
    """

    def __init__(self):
        self._agents: dict[str, Agent] = {}

    # ============================================================
    # 配置读取
    # ============================================================

    def load_role_config(self, role_id: str) -> dict | None:
        """读取角色的 role_config.yaml"""
        config_path = os.path.join(ROLES_DIR, role_id, "role_config.yaml")
        if not os.path.exists(config_path):
            return None
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def load_claude_md(self, role_id: str) -> str:
        """读取角色的 claude.md 人设文件"""
        md_path = os.path.join(ROLES_DIR, role_id, "claude.md")
        if not os.path.exists(md_path):
            return ""
        with open(md_path, "r", encoding="utf-8") as f:
            return f.read()

    def list_role_ids(self) -> list[str]:
        """列出所有已配置的角色ID (扫描 roles/ 目录)"""
        if not os.path.exists(ROLES_DIR):
            return []
        return [
            d for d in os.listdir(ROLES_DIR)
            if os.path.isdir(os.path.join(ROLES_DIR, d))
            and os.path.exists(os.path.join(ROLES_DIR, d, "role_config.yaml"))
            and not d.startswith("_") and not d.startswith(".")
        ]

    # ============================================================
    # Agent 创建
    # ============================================================

    def create_agent(self, role_id: str) -> Agent | None:
        """
        从文件配置创建 CrewAI Agent

        步骤:
          1. 读取 role_config.yaml → 获取 role/goal/tools/crewai参数
          2. 读取 claude.md → 作为 backstory
          3. 从 tool_registry 获取绑定的工具实例
          4. 创建 CrewAI Agent
        """
        config = self.load_role_config(role_id)
        if not config:
            print(f"[AgentFactory] 角色 '{role_id}' 的配置文件不存在, 跳过")
            return None

        backstory = self.load_claude_md(role_id)

        # 获取绑定的工具
        tool_names = config.get("tools", [])
        tools = []
        for tname in tool_names:
            tool = tool_registry.get_tool(tname)
            if tool:
                tools.append(tool)

        # 创建 CrewAI Agent
        crewai_opts = config.get("crewai", {})
        agent = Agent(
            role=config.get("title", config.get("name", role_id)),
            goal=config.get("goal", ""),
            backstory=backstory or config.get("goal", ""),
            tools=tools if tools else None,
            verbose=crewai_opts.get("verbose", True),
            allow_delegation=crewai_opts.get("allow_delegation", False),
            max_iter=crewai_opts.get("max_iter", 10),
            llm=None,  # 执行由现有 llm_client 流程驱动
        )

        self._agents[role_id] = agent
        return agent

    def create_all(self):
        """批量创建所有已配置角色的 Agent"""
        for role_id in self.list_role_ids():
            self.create_agent(role_id)

    # ============================================================
    # Agent 查询
    # ============================================================

    def get_agent(self, role_id: str) -> Agent | None:
        """获取已创建的 Agent (自动创建)"""
        if role_id not in self._agents:
            self.create_agent(role_id)
        return self._agents.get(role_id)

    def get_agent_config(self, role_id: str) -> dict | None:
        """
        获取 Agent 的完整配置摘要 (供 API/UI展示)

        合并 role_config.yaml + claude.md 信息
        """
        config = self.load_role_config(role_id)
        if not config:
            return None

        backstory = self.load_claude_md(role_id)
        tools = tool_registry.get_tools_for_role(role_id)
        memory_info = config.get("memory", {})

        return {
            "role_id": config.get("role_id", role_id),
            "name": config.get("name", ""),
            "title": config.get("title", ""),
            "icon": config.get("icon", ""),
            "goal": config.get("goal", ""),
            "backstory_preview": backstory[:300] + "..." if len(backstory) > 300 else backstory,
            "tools": [
                {"name": t.name, "category": t.tool_category}
                for t in tools
            ],
            "permissions": config.get("permissions", {}),
            "crewai_opts": config.get("crewai", {}),
            "memory_config": {
                "short_term_max": memory_info.get("short_term_max", 50),
                "long_term_auto_save": memory_info.get("long_term_auto_save", True),
            },
            "has_claude_md": len(backstory) > 0,
            "config_path": f"roles/{role_id}/role_config.yaml",
            "claude_md_path": f"roles/{role_id}/claude.md",
        }

    def list_all(self) -> list[dict]:
        """列出所有已配置角色的摘要"""
        return [
            self.get_agent_config(rid)
            for rid in self.list_role_ids()
        ]

    # ============================================================
    # 配置写入 (可编辑弹窗)
    # ============================================================

    # UI可编辑字段白名单 (role_id/name/title/icon 不可编辑)
    _EDITABLE_FIELDS = {"goal", "tools", "permissions", "crewai", "memory"}

    def save_role_config(self, role_id: str, updates: dict) -> tuple[bool, str]:
        """
        将UI提交的配置写回 role_config.yaml

        仅允许写入白名单字段, 保留不可编辑字段不变
        返回 (success, message)
        """
        config_path = os.path.join(ROLES_DIR, role_id, "role_config.yaml")
        if not os.path.exists(config_path):
            return False, f"角色 '{role_id}' 的配置文件不存在"

        current = self.load_role_config(role_id)
        if not current:
            return False, f"无法读取角色 '{role_id}' 的配置"

        for key in updates:
            if key in self._EDITABLE_FIELDS:
                current[key] = updates[key]

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(current, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            # 清除缓存, 下次读取时重新加载
            if role_id in self._agents:
                del self._agents[role_id]
            return True, "保存成功"
        except Exception as e:
            return False, f"写入失败: {str(e)}"

    def save_claude_md(self, role_id: str, content: str) -> tuple[bool, str]:
        """
        将UI编辑的文本写回 claude.md 人设手册

        返回 (success, message)
        """
        md_path = os.path.join(ROLES_DIR, role_id, "claude.md")
        if not os.path.exists(md_path):
            return False, f"角色 '{role_id}' 的 claude.md 不存在"

        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(content)
            # 清除缓存
            if role_id in self._agents:
                del self._agents[role_id]
            return True, "保存成功"
        except Exception as e:
            return False, f"写入失败: {str(e)}"

    @property
    def count(self) -> int:
        """已配置的角色数量"""
        return len(self._agents)

    @property
    def role_ids(self) -> list[str]:
        """所有已配置的角色ID"""
        return self.list_role_ids()


# ============================================================
# 全局单例
# ============================================================
agent_factory = AgentFactory()
