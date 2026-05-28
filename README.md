# ClaudeCompany · 可视化自进化多AI团队协同系统

基于 **Flask + CrewAI + Claude Code** 构建的商用级多AI团队协同系统。模拟真实软件开发团队——管理AI拆解需求、前端/后端/测试AI各司其职、质控引擎自动审查、自进化引擎持续优化。

## 设计理念

```
原有 Flask Demo (界面/终端/双模式/事件总线/workspace)
+ CrewAI 四元底座 (Agent/Task/Tool/Crew)
+ 一人一目录多员工体系 (YAML配置 + claude.md人设 + 分层记忆)
+ 自研六层架构 (管控/可视化/统筹/执行/质控进化/持久)
```

**核心原则：** 增量不推翻、文件化配置零硬编码、一人一档、模块解耦。

## 快速开始

### 环境要求

- Python 3.9+
- Claude Code CLI（仅 `claude` 模式需要）

### 安装与启动

```bash
cd ClaudeCompany
pip install -r requirements.txt

# 配置环境（可选，默认值即可运行）
cp .env.example .env

# 启动
python app.py                    # 手动启动
# 或双击 start.bat (Windows) / ./start.sh (macOS/Linux)
```

浏览器打开 **http://127.0.0.1:5000**

### 切换运行模式

编辑 `.env` 中的 `AI_MODE`：

| 值 | 说明 |
|----|------|
| `claude` | 真实 Claude Code CLI 驱动（默认） |
| `simulated` | Python 线程模拟，无需 CLI，适合开发调试 |

### 使用流程

1. **对话 Tab** — 输入开发需求（如"创建一个登录页面"），管理AI自动拆解并调度
2. **任务 Tab** — 查看各AI员工的执行进度和产出
3. **代码 Tab** — 浏览生成的前端/后端/测试代码
4. **监控 Tab** — 查看角色配置、记忆状态、工具调用统计、系统仪表盘

## 架构

### 六层架构

```
┌─────────────────────────────────────────────────┐
│  第1层: 人类管控层 (human_control/)              │
│  审批/驳回/启停/告警                              │
├─────────────────────────────────────────────────┤
│  第2层: 可视化交互层 (Flask + SSE)                │
│  Web界面/实时事件流/任务面板/监控仪表盘            │
├─────────────────────────────────────────────────┤
│  第3层: AI动态统筹层 (core/dynamic_scheduler.py)  │
│  智能任务拆解/动态分配/负载感知/自动重试            │
├─────────────────────────────────────────────────┤
│  第4层: 专业化执行集群 (roles/ + tools/)          │
│  CrewAI Agent标准化/Claude工具封装/专人专岗        │
├─────────────────────────────────────────────────┤
│  第5层: 质控&进化层 (quality_evolve/)             │
│  代码质控/冲突调解/趋势分析/复盘报告/经验沉淀       │
├─────────────────────────────────────────────────┤
│  第6层: 统一持久层 (core/data_store.py)           │
│  SQLite全量存储/三层记忆/JSON持久化                │
└─────────────────────────────────────────────────┘
```

### 团队协作模型

```
人类负责人 (Web UI)
    ↕ 对话 + 审批
管理AI (Manager)
    ↕ 任务拆解 + 调度分配
┌──────────┬──────────┬──────────┐
│ 前端AI    │ 后端AI    │ 测试AI    │
│ HTML/CSS  │ Python/  │ pytest   │
│ /JS       │ Flask    │          │
└──────────┴──────────┴──────────┘
    ↕ 各自专属工具 + 独立记忆
代码工作区 (workspace/)
    ↓
质控引擎 → 冲突调解 → 项目交付
    ↓
自进化引擎 → 复盘报告 → 经验沉淀
```

### 记忆体系

```
任务开始 → 加载上下文(短期+长期+团队) → 注入prompt
任务执行 → remember() → short_term.json 累积
任务完成 → complete_task() → long_term.md 归档 + SQLite索引
```

| 层级 | 存储位置 | 生命周期 |
|------|----------|----------|
| 短期记忆 | `roles/*/memory/short_term.json` | 单次任务，完成自动清空 |
| 长期记忆 | `roles/*/memory/long_term.md` | 永久保留，AI自动追加+人工编辑 |
| 团队记忆 | `memory_center/team_shared.md` | 全员共享，永久保留 |

## 项目结构

```
ClaudeCompany/
├── app.py                      # Flask 主入口，15+ API 路由
├── config.py                   # Python 配置模块
├── config.yaml                 # YAML 全局配置
├── .env                        # 密钥/环境变量
├── requirements.txt            # Python 依赖
├── start.bat / start.sh        # 一键启动脚本
│
├── core/                       # 核心引擎
│   ├── manager_chat.py         # 管理AI对话引擎（六层流水线）
│   ├── manager_ai.py           # 管理AI模拟模式
│   ├── background_worker.py    # 后台Claude执行器
│   ├── llm_client.py           # Claude CLI统一调用封装
│   ├── dynamic_scheduler.py    # 动态调度器（依赖排序/负载/重试）
│   ├── memory_manager.py       # 三层记忆管理器
│   ├── data_store.py           # SQLite数据仓库（7张表）
│   ├── event_bus.py            # 发布/订阅事件总线
│   ├── bulletin_board.py       # AI间协作公告板
│   ├── workspace.py            # 代码工作区（文件锁/原子写入）
│   ├── task_manager.py         # 任务生命周期管理
│   ├── persistence.py          # JSON状态持久化
│   ├── executor_ai.py          # 执行AI基类
│   └── terminal_launcher.py    # 多窗口终端启动器
│
├── roles/                      # 多员工角色体系（一人一目录）
│   ├── manager/                # 管理AI
│   │   ├── role_config.yaml    # 角色配置
│   │   ├── claude.md           # 人设手册
│   │   └── memory/             # 个人记忆
│   ├── frontend_dev/           # 前端开发AI
│   │   ├── role_config.yaml
│   │   ├── claude.md
│   │   ├── simulated.py        # 模拟模式代码生成
│   │   └── memory/
│   ├── backend_dev/            # 后端开发AI
│   └── tester/                 # 测试AI
│
├── crew_adapter/               # CrewAI 适配层
│   └── agent_factory.py        # 动态Agent工厂（读配置→创建Agent）
│
├── tools/                      # Claude 工具库（CrewAI标准接口）
│   ├── base.py                 # ClaudeBaseTool 基类
│   ├── registry.py             # 工具注册中心（权限+可插拔）
│   ├── code_tool.py            # 代码执行工具
│   ├── file_tool.py            # 文件读写分析工具
│   ├── search_tool.py          # 技术搜索工具
│   └── debug_tool.py           # 调试报错分析工具
│
├── quality_evolve/             # 质控 & 进化层
│   ├── checker.py              # 代码质控（文件存在/API一致性/内容）
│   ├── conflict_resolver.py    # 冲突调解（自动/人工）
│   └── evolver.py              # 自进化（趋势分析/经验沉淀/复盘）
│
├── human_control/              # 人类管控层
│   └── approval.py             # 审批/驳回/启停/告警
│
├── memory_center/              # 全局团队记忆
│   └── team_shared.md          # 规范/经验/FAQ
│
├── templates/                  # Flask HTML 模板
│   ├── index.html              # 主界面（对话/任务/代码/监控）
│   └── about.html              # 公司介绍
│
├── static/                     # 前端资源
│   ├── css/style.css           # 暗色终端主题
│   └── js/app.js               # SSE 实时通信 + 四面板逻辑
│
└── workspace/                  # AI 代码产出目录
    ├── frontend/ backend/ tests/  # 临时工作区
    ├── projects/               # 交付项目归档
    ├── _state/                 # 持久化数据
    │   ├── data.db             # SQLite 数据库
    │   ├── chat_history.json   # 对话历史
    │   └── tasks.json          # 任务状态
    └── _board/                 # AI 公告板
```

## 功能特性

### 意图识别（双路径 + 统一校验）

系统根据运行模式采用两套意图识别路径，共享同一个校验层。

**Path A: Claude 模式 — LLM 驱动的六层流水线**（`core/manager_chat.py`）

```
人类输入
  ↓
第1层 预处理     → 注入上轮任务执行反馈到对话历史
第2层 意图理解   → Claude 根据系统提示词判断：聊天/追问/派活
第3层 解析校验   → 提取 <<<DELEGATE>>> JSON，四重校验
  ↓
输出: 文本回复 + 任务列表
```

第2层使用 `MANAGER_SYSTEM_PROMPT`（`config.py`）定义调度原则：

| 需求类型 | 派发策略 |
|----------|----------|
| 纯 UI（样式、页面） | 只派前端 |
| 纯后端（API、数据库） | 只派后端 |
| 全栈（登录、注册） | 前端 + 后端 |
| 测试 | 只派测试 |
| 复杂全栈 | 三个全派 |

第3层四重校验（`core/dynamic_scheduler.py`）：

| 校验项 | 失败处理 |
|--------|----------|
| 角色是否存在 | 阻塞，回流反馈 |
| 角色是否空闲（≤1并发） | 阻塞，进入等待队列 |
| 依赖角色是否可满足 | 警告，不阻塞 |
| 任务描述 ≥10字 | 警告，不阻塞 |

**Path B: Simulated 模式 — 关键词匹配**（`core/manager_ai.py`）

```
页面/界面/UI/前端/登录/表单/按钮/列表/表格 → 派前端
API/接口/后端/数据/存储/查询/服务/数据库    → 派后端
（总是追加）                              → 派测试
无关键词匹配                              → 默认前端+后端+测试
```

**设计原则：LLM 做意图，代码做校验。** Claude 决定派谁派什么，但角色存在性、负载、依赖由代码机械校验，不信任 LLM 输出。执行结果通过反馈缓冲区回流到下一轮对话，形成自适应闭环。

### 管理AI对话引擎
- 六层流水线：反馈注入 → Claude调用 → DELEGATE协议解析 → 校验 → 响应
- 支持 `<<<DELEGATE>>>` JSON 块自动拆解需求并派发子任务
- 角色存在性/负载/依赖性三重校验

### 动态调度器
- 依赖排序优化，自动识别父子任务链
- 每角色最多 1 个并发任务，最多 2 次自动重试
- 历史耗时参考，负载感知分配

### 四大Claude工具
| 工具 | 功能 | 绑定角色 |
|------|------|----------|
| `code_tool` | 代码生成执行 | 前端 + 后端 |
| `file_tool` | 文件读写/列表/分析 | 全部 |
| `search_tool` | 代码搜索/技术查询/依赖分析 | 全部 |
| `debug_tool` | 错误根因分析/修复方案 | 测试 |

### 质控 & 进化
- **代码质控**: 文件存在性检查、API 一致性校验（前端 fetch ↔ 后端 route）、内容有效性验证
- **冲突调解**: 同名文件冲突检测、API 不匹配、低风险自动解决 + 高风险人工审查
- **自进化**: 错误频率趋势分析、角色效率评估、工具使用统计、自动复盘报告

### Web 可视化界面
- 暗色终端主题，四面板布局（对话/任务/代码/监控）
- SSE 实时事件流，20+ 事件类型
- 角色配置在线编辑、记忆查看/添加、人设手册编辑器
- 系统仪表盘含概览指标、流水线、错误日志、工具统计

## 配置体系

```
config.yaml              → 全局非敏感配置（端口/模式/角色注册/模拟参数）
.env                     → 密钥/模型/运行模式
roles/*/role_config.yaml → 角色配置（目标/工具/权限/CrewAI参数）
roles/*/claude.md        → 角色人设（身份/职责/协作规则/输出格式）
roles/*/memory/          → 个人记忆（short_term.json + long_term.md）
memory_center/           → 团队共享记忆（team_shared.md）
```

### 添加新员工

```bash
mkdir -p roles/new_role/memory
# 创建 roles/new_role/role_config.yaml（参考 frontend_dev）
# 创建 roles/new_role/claude.md（编写岗位手册）
# 在 config.yaml 的 roles 列表中注册
```

## API 概览

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/chat` | POST | 发送需求给管理AI |
| `/api/status` | GET | AI状态 + 任务列表 |
| `/api/events` | GET | SSE 实时事件流 |
| `/api/task/<id>/approve` | POST | 审批通过 |
| `/api/task/<id>/reject` | POST | 驳回任务 |
| `/api/task/<id>/stop` | POST | 强制停止 |
| `/api/board` | GET | 公告板内容 |
| `/api/workspace/tree` | GET | 文件树 |
| `/api/workspace/file` | GET | 文件内容 |
| `/api/roles` | GET | 角色配置预览 |
| `/api/roles/<id>` | GET/POST | 角色详情查询/更新 |
| `/api/memories/<role_id>` | GET/POST | 角色记忆查看/添加 |
| `/api/tool-logs` | GET | 工具调用日志 |
| `/api/system/overview` | GET | 系统仪表盘 |
| `/api/reset` | POST | 重置系统 |

## 技术栈

| 类别 | 技术 |
|------|------|
| Web 框架 | Flask + SSE |
| AI 引擎 | CrewAI + Claude Code CLI |
| 数据库 | SQLite（WAL 模式，7 张表） |
| 配置 | YAML + .env |
| 记忆 | JSON（短期）+ Markdown（长期/团队） |
| 前端 | 原生 HTML/CSS/JS（暗色终端主题） |
| Python | 3.9+ |
