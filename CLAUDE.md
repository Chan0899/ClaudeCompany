# ClaudeCompany · 多AI团队协同系统

## 项目概述

基于 Flask + CrewAI + Claude Code 构建的可视化多AI团队协同系统。模拟真实软件开发团队：管理AI拆解需求、前端/后端/测试AI各司其职、质控引擎自动审查、自进化引擎持续优化。

## 运行方式

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 (二选一)
python app.py          # 手动启动
./start.bat            # Windows 一键启动
./start.sh             # macOS/Linux 一键启动
```

浏览器打开 `http://127.0.0.1:5000`。

## 双运行模式

通过 `.env` 中的 `AI_MODE` 切换：

| 值 | 说明 |
|----|------|
| `claude` | 真实 Claude Code CLI 驱动，需安装 `claude` 命令 |
| `simulated` | Python 线程模拟，无需 CLI，用于开发调试 |

## 架构

### 六层架构

```
第1层: 人类管控层 (human_control/)     — 审批/驳回/启停/告警
第2层: 可视化交互层 (Flask + templates) — Web界面/SSE实时推送/监控仪表盘
第3层: AI动态统筹层 (core/scheduler)    — 任务拆解/动态分配/负载感知/自动重试
第4层: 专业化执行集群 (roles/ + tools/)  — 一人一目录/Claude工具封装/专人专岗
第5层: 质控&进化层 (quality_evolve/)    — 代码质控/冲突调解/趋势分析/经验沉淀
第6层: 统一持久层 (core/data_store.py)  — SQLite全量存储/三层记忆/JSON持久化
```

### 团队协作流程

```
人类负责人 (Web UI)
    ↓ 对话 + 审批
管理AI (Manager) → 拆解需求 → 派发任务
    ↓
┌──────────┬──────────┬──────────┐
│ 前端AI    │ 后端AI    │ 测试AI    │
│ HTML/CSS  │ Python/  │ pytest   │
│ /JS       │ Flask    │          │
└──────────┴──────────┴──────────┘
    ↓ 产出代码
代码工作区 (workspace/)
    ↓
质控引擎 → 冲突调解 → 项目交付归档
    ↓
自进化引擎 → 复盘报告 → 经验写入记忆
```

## 意图识别机制

系统根据运行模式采用两套意图识别路径，共享同一个校验层。

### Path A: Claude 模式 — LLM 驱动的六层流水线

`core/manager_chat.py` 实现了完整的意图识别流水线：

```
人类输入
  ↓
第1层 预处理: 注入上轮任务执行反馈（完成/失败/重试/阻塞）到对话历史
  ↓
第2层 意图理解: 调用 Claude，携带 MANAGER_SYSTEM_PROMPT（含调度原则）
  ↓
第3层 解析校验: 从回复中提取 <<<DELEGATE>>> JSON，校验角色/负载/依赖
  ↓
输出: 纯文本回复 + 校验后的任务列表（或 None）
```

**第2层核心 — 系统提示词调度原则**（`config.py:MANAGER_SYSTEM_PROMPT`）：

| 需求类型 | 派发策略 |
|----------|----------|
| 纯 UI（改样式、新页面） | 只派前端 |
| 纯后端（API、数据库） | 只派后端 |
| 全栈（登录、注册） | 前端 + 后端 |
| 测试 | 只派测试 |
| 复杂全栈 | 三个全派 |

Claude 自行决定三种行为：**纯聊天**（需求不明确时追问）、**直接回复**（无需派活）、**输出 `<<<DELEGATE>>>` JSON 块**（派活）。第2层只注入团队记忆，不注入调度上下文，避免干扰 Claude 的判断。

**第3层核心 — 四重校验**（`core/dynamic_scheduler.py:validate_delegation()`）：

| 校验项 | 类型 | 处理 |
|--------|------|------|
| 角色是否存在 | `role_unknown` | 阻塞，写入反馈队列 |
| 角色是否空闲（每角色最多1并发） | `role_overloaded` | 阻塞，进入等待队列 |
| 依赖角色是否可满足 | `dependency_unknown` | 警告，不阻塞 |
| 任务描述是否 ≥10 字 | `description_too_short` | 警告，不阻塞 |

校验失败的阻塞任务通过 feedback 缓冲区回流到下一轮对话的第1层，管理AI据此调整计划。

### Path B: Simulated 模式 — 关键词匹配

`core/manager_ai.py:_decompose()` 扫描需求中的中英文关键词：

```
页面/界面/UI/前端/登录/表单/按钮/展示/列表/表格 → 派前端
API/接口/后端/数据/注册/存储/查询/服务/逻辑/数据库 → 派后端
（总是追加）→ 派测试
无关键词匹配 → 默认派前端+后端+测试
```

### 设计要点

- **LLM 做意图，代码做校验**：Claude 决定"派谁、派什么"，但角色存在性、负载、依赖由代码机械校验，不信任 LLM 输出
- **两路径共享校验层**：无论 Claude 还是 Simulated，最终都经过 `validate_delegation()` 和 `ExecutionController` 的负载/重试控制
- **反馈闭环**：执行结果回流到对话历史，管理AI能感知任务状态并自适应调整

## 核心约定

### 配置体系（禁止硬编码）

```
config.yaml              — 全局非敏感配置（端口/模式/角色注册/模拟参数）
.env                     — 密钥/模型/运行模式
roles/*/role_config.yaml — 角色配置（目标/工具/权限/CrewAI参数）
roles/*/claude.md        — 角色人设手册（身份/职责/协作规则/输出格式）
roles/*/memory/          — 个人记忆（short_term.json + long_term.md）
memory_center/           — 团队共享记忆（team_shared.md）
```

### 一人一目录

每个AI员工独立目录，包含 `role_config.yaml` + `claude.md` + `memory/`。新增员工只需创建目录和两个文件，然后在 `config.yaml` 的 `roles` 列表中注册。

### 三层记忆

| 层级 | 存储 | 生命周期 |
|------|------|----------|
| 短期记忆 | `roles/*/memory/short_term.json` | 单次任务，完成归档后清空 |
| 长期记忆 | `roles/*/memory/long_term.md` | 永久保留，AI自动追加 |
| 团队记忆 | `memory_center/team_shared.md` | 永久保留，全员可读 |

### 文件格式

- 配置: YAML
- 人设/长期记忆/团队记忆: Markdown
- 短期记忆: JSON
- 持久化: SQLite（WAL模式，7张表）

## 编码规范

- 所有新增模块独立解耦，不修改 CrewAI 源码
- 配置驱动，代码中不硬编码角色信息、工具绑定、模型参数
- 模型统一使用 Claude Code 系列，不接入 OpenAI
- 中文注释，变量语义化

## 关键文件索引

| 文件 | 职责 |
|------|------|
| `app.py` | Flask 主入口，15+ API 路由，SSE 事件流 |
| `core/manager_chat.py` | 管理AI对话引擎，六层流水线，`<<<DELEGATE>>>` 协议解析 |
| `core/background_worker.py` | 后台 Claude 执行器，角色 prompt 构建，流式输出 |
| `core/dynamic_scheduler.py` | 动态调度器，依赖排序，负载控制，自动重试 |
| `core/memory_manager.py` | 三层记忆管理器，自动归档，SQLite 同步 |
| `core/data_store.py` | SQLite 数据仓库，7张表，线程安全 |
| `core/llm_client.py` | 统一 Claude CLI 调用封装，支持流式/同步 |
| `core/event_bus.py` | 进程内发布/订阅事件总线 |
| `core/workspace.py` | 代码工作区，文件锁，原子写入 |
| `crew_adapter/agent_factory.py` | CrewAI Agent 动态工厂，读配置创建 Agent |
| `tools/` | 四大工具（代码执行/文件操作/技术搜索/调试分析），CrewAI BaseTool 标准接口 |
| `quality_evolve/` | 质控检查/冲突调解/自进化复盘 |
| `human_control/approval.py` | 审批/驳回/启停/告警 |

## 常见操作

### 添加新角色

```bash
mkdir -p roles/new_role/memory
# 创建 roles/new_role/role_config.yaml（参考 frontend_dev）
# 创建 roles/new_role/claude.md（编写岗位手册）
# 在 config.yaml 的 roles 列表中注册
```

### 调试

- 设置 `AI_MODE=simulated`，所有 AI 调用走本地模拟，无需 Claude CLI
- 查看 `workspace/_state/data.db`，工具调用/任务记录/错误日志全量入库
- 浏览器打开监控 Tab 查看实时仪表盘
