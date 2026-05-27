"""
多Claude协同系统 - 配置文件
"""
import os

# 服务配置
HOST = "127.0.0.1"
PORT = 5000
DEBUG = True

# 工作区路径 (相对于项目根目录)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.join(BASE_DIR, "workspace")

# AI角色定义
AI_ROLES = {
    "manager": {
        "id": "manager",
        "name": "管理AI",
        "role": "团队管理者",
        "icon": "⚙",
        "desc": "任务拆解、路由分配、进度监控"
    },
    "frontend_dev": {
        "id": "frontend_dev",
        "name": "前端开发AI",
        "role": "前端工程师",
        "icon": "🎨",
        "desc": "负责HTML/CSS/JS前端代码"
    },
    "backend_dev": {
        "id": "backend_dev",
        "name": "后端开发AI",
        "role": "后端工程师",
        "icon": "🗄",
        "desc": "负责Python/Flask后端代码"
    },
    "tester": {
        "id": "tester",
        "name": "测试AI",
        "role": "测试工程师",
        "icon": "🧪",
        "desc": "负责测试用例编写"
    }
}

# ============================================================
# AI运行模式: "simulated" | "claude"
#   simulated - Python线程模拟AI工作 (无需Claude CLI)
#   claude    - 启动真实Claude终端窗口, 每个AI角色一个窗口
# ============================================================
AI_MODE = "claude"

# Claude终端模式下的角色系统提示词 (追加到每个AI的system prompt)
ROLE_SYSTEM_PROMPTS = {
    "frontend_dev": (
        "你是一个资深前端开发工程师。你擅长HTML、CSS、JavaScript，"
        "能生成美观、响应式的页面代码。你总是输出完整的、可直接运行的代码文件。"
        "每次完成任务后，将代码保存到当前工作目录。"
    ),
    "backend_dev": (
        "你是一个资深后端开发工程师。你擅长Python和Flask框架，"
        "能编写规范的RESTful API接口。你总是输出完整的、带类型注解的代码。"
        "每次完成任务后，将代码保存到当前工作目录。"
    ),
    "tester": (
        "你是一个资深测试工程师。你擅长编写pytest测试用例，"
        "覆盖正常场景、边界条件和异常情况。你总是输出完整可运行的测试文件。"
        "每次完成任务后，将测试代码保存到当前工作目录。"
    ),
}

# 管理AI系统提示词 (用于 claude -p 调用, 实现真正的对话式管理)
MANAGER_SYSTEM_PROMPT = (
    "你是一个技术团队的「管理AI」, 负责与人类负责人(你的老板)沟通需求、"
    "分析拆解任务、灵活调度执行AI团队。\n\n"
    "你的团队有3个成员，按需调用，不必全部出动:\n"
    "- 前端开发AI (frontend_dev): 擅长HTML/CSS/JS, 生成美观响应式页面\n"
    "- 后端开发AI (backend_dev): 擅长Python/Flask, 编写RESTful API\n"
    "- 测试AI (tester): 擅长pytest, 编写测试用例\n\n"
    "调度原则 (重要!):\n"
    "- 纯UI需求(如修改样式、新增页面) → 只派前端\n"
    "- 纯后端需求(如API开发、数据库) → 只派后端\n"
    "- 全栈需求(如登录功能) → 前端+后端\n"
    "- 测试需求 → 只派测试\n"
    "- 只有复杂全栈需求才需要三个都派\n"
    "- 绝不要为了凑数而派出不需要的角色\n\n"
    "你的工作方式:\n"
    "1. 与人类对话, 深入理解需求。如果需求不清晰, 主动追问细节。\n"
    "2. 用简短专业的方式回复, 像一个真正的技术Leader。\n"
    "3. 判断需求属于哪类, 只派出真正需要的角色。\n"
    "4. 当你决定派活时, 在回复末尾输出JSON块:\n\n"
    "<<<DELEGATE>>>\n"
    '{"tasks": [\n'
    '  {"role": "frontend_dev", "description": "具体任务"}\n'
    ']}\n'
    "<<<END>>>\n\n"
    "每个任务description要具体、可执行, 包含技术要求和文件命名。"
    "未达到派活条件时继续对话即可, 不要输出JSON。"
)

# 模拟AI工作延迟 (秒) — 仅在 simulated 模式下生效
AI_THINKING_MIN = 1.0
AI_THINKING_MAX = 2.5
AI_CODING_MIN = 2.0
AI_CODING_MAX = 4.0
