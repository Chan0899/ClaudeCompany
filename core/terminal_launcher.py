"""
终端启动器 - 为每个AI角色打开独立的Claude终端窗口

Windows: 通过PowerShell + Start-Process 打开新窗口
每个窗口独立运行 claude CLI, 角色身份通过 --append-system-prompt 注入
"""
import os
import subprocess
from config import WORKSPACE_DIR, ROLE_SYSTEM_PROMPTS


def build_task_prompt(role_name: str, task_description: str, feature: str, workspace_subdir: str) -> str:
    """为指定角色构造任务提示词"""
    role_dir = os.path.join(WORKSPACE_DIR, workspace_subdir)

    return (
        f"你是{role_name}。请完成以下开发任务：\n\n"
        f"【任务】{task_description}\n"
        f"【所属功能】{feature}\n\n"
        f"要求：\n"
        f"1. 将生成的完整代码文件保存到 {role_dir} 目录\n"
        f"2. 代码要完整、可直接运行、不要省略任何部分\n"
        f"3. 如果是前端代码，确保HTML/CSS/JS都在一个文件中、样式美观\n"
        f"4. 如果是后端代码，确保有完整的API实现和错误处理\n"
        f"5. 如果是测试代码，覆盖正常场景、边界条件和异常情况\n"
        f"6. 完成后简要说明你生成了哪些文件\n\n"
        f"请开始工作。"
    )


def launch_claude_terminal(
    role_id: str,
    role_name: str,
    workspace_subdir: str,
    task_description: str,
    feature: str
):
    """
    为指定AI角色打开一个新的Claude终端窗口

    参数:
        role_id: 角色ID (frontend_dev, backend_dev, tester)
        role_name: 角色显示名 (前端开发AI, ...)
        workspace_subdir: 工作区子目录 (frontend, backend, tests)
        task_description: 任务描述
        feature: 所属功能名称
    """
    role_dir = os.path.join(WORKSPACE_DIR, workspace_subdir)
    os.makedirs(role_dir, exist_ok=True)

    # 构造任务提示词
    task_prompt = build_task_prompt(role_name, task_description, feature, role_dir)

    # 获取角色专属系统提示词
    system_prompt = ROLE_SYSTEM_PROMPTS.get(role_id, "")

    # 将任务提示词写入文件 (避免命令行转义问题)
    prompt_file = os.path.join(role_dir, "_TASK.md")
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(f"# {role_name} - 任务\n\n{task_prompt}")

    # 构造PowerShell启动脚本
    # 从文件读取任务内容, 通过管道传给 claude -p
    ps_script = f'''
$host.ui.RawUI.WindowTitle = "{role_name} - Claude"

Write-Host ""
Write-Host "╔════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  {role_name} - Claude 终端" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "  任务: {task_description[:40]}..." -ForegroundColor Yellow
Write-Host "  目录: {role_dir}" -ForegroundColor Yellow
Write-Host ""

# 读取任务内容
$taskContent = Get-Content -Path "{prompt_file}" -Raw -Encoding UTF8

Write-Host ">>> 启动Claude, 执行任务..." -ForegroundColor Green
Write-Host ""

# 执行Claude (非交互模式)
claude -p $taskContent --append-system-prompt "{system_prompt}"

Write-Host ""
Write-Host "<<< Claude任务执行完毕" -ForegroundColor Green
Write-Host ""
Read-Host "按Enter关闭此窗口"
'''

    # 写入PowerShell脚本文件
    script_path = os.path.join(role_dir, f"_launch_{role_id}.ps1")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(ps_script)

    # 启动新PowerShell窗口 (使用 start 命令, Windows最可靠的方式)
    try:
        subprocess.Popen(
            f'start "{role_name} - Claude" powershell -NoExit -ExecutionPolicy Bypass -File "{script_path}"',
            shell=True
        )
        return True
    except Exception as e:
        print(f"[TerminalLauncher] 启动 {role_name} 终端失败: {e}")
        return False


def launch_manager_terminal(feature: str):
    """
    为管理AI打开一个Claude终端窗口 (用于复杂需求的深度分析)
    """
    manager_dir = os.path.join(WORKSPACE_DIR, "manager")
    os.makedirs(manager_dir, exist_ok=True)

    task_prompt = (
        f"你是管理AI（团队管理者），收到以下人类需求：\n\n"
        f"「{feature}」\n\n"
        f"请完成以下工作：\n"
        f"1. 深入分析这个需求，拆解为前端、后端、测试三个维度的具体子任务\n"
        f"2. 对每个子任务给出详细的技术要求和验收标准\n"
        f"3. 将分析结果保存到 {manager_dir}/analysis.md\n\n"
        f"请开始分析。"
    )

    prompt_file = os.path.join(manager_dir, "_TASK.md")
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(f"# 管理AI - 需求分析\n\n{task_prompt}")

    ps_script = f'''
$host.ui.RawUI.WindowTitle = "管理AI - Claude"

Write-Host ""
Write-Host "╔════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║  管理AI - Claude 终端" -ForegroundColor Magenta
Write-Host "╚════════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""
Write-Host "  需求: {feature}" -ForegroundColor Yellow
Write-Host ""

$taskContent = Get-Content -Path "{prompt_file}" -Raw -Encoding UTF8

Write-Host ">>> 启动Claude, 分析需求..." -ForegroundColor Green
Write-Host ""

claude -p $taskContent --append-system-prompt "你是一个技术团队管理者，擅长需求分析和任务拆解。做决策果断清晰。"

Write-Host ""
Write-Host "<<< 分析完成" -ForegroundColor Green
Write-Host ""
Read-Host "按Enter关闭此窗口"
'''

    script_path = os.path.join(manager_dir, "_launch_manager.ps1")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(ps_script)

    try:
        subprocess.Popen(
            f'start "管理AI - Claude" powershell -NoExit -ExecutionPolicy Bypass -File "{script_path}"',
            shell=True
        )
        return True
    except Exception as e:
        print(f"[TerminalLauncher] 启动管理AI终端失败: {e}")
        return False
