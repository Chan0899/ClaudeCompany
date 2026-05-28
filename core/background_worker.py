"""
后台Claude执行器 - 通过统一 LLM Client 调用, 输出通过SSE实时推送

模块1适配: 替换 subprocess.Popen 为 llm_client.chat_stream()

Fix 1: 注入公告板上下文, AI间可协作
Fix 3: 测试AI拿到实际代码后针对性测试
"""
import os
import threading
from config import WORKSPACE_DIR, ROLE_SYSTEM_PROMPTS
from core.event_bus import event_bus
from core.bulletin_board import board, BOARD_FILE
from core.workspace import workspace
from core.llm_client import llm_client
from core.memory_manager import get_memory_manager


def run_claude_worker(
    role_id: str,
    role_name: str,
    workspace_subdir: str,
    task_description: str,
    feature: str,
    task_id: str = None,
    extra_context: str = ""
):
    """
    后台启动Claude执行任务, 输出实时流到SSE

    在独立线程中运行, 不阻塞主流程。
    通过 event_bus 发布: log, worker_output, worker_done, ai_status, board_post
    """
    role_dir = os.path.join(WORKSPACE_DIR, workspace_subdir)
    os.makedirs(role_dir, exist_ok=True)

    system_prompt = ROLE_SYSTEM_PROMPTS.get(role_id, "")

    # 读取公告板上下文 (Fix 1: AI间通信)
    board_content = board.read_recent()
    board_section = ""
    if board_content.strip() and len(board_content) > 50:
        board_section = (
            "\n\n【协作公告板 - 其他AI的最新消息】\n"
            f"{board_content[-2000:]}\n\n"
            "如果需要与其他AI协调(如确认API格式、文件命名), "
            f"请将消息追加写入 {BOARD_FILE}\n"
            "格式: ## [你的角色名] @ 时间\n你的消息内容\n"
        )

    # Fix 3: 测试AI需要看到实际代码
    tester_context = ""
    if role_id == "tester":
        all_files = workspace.list_all_code_files()
        code_snippets = []
        for role, files in all_files.items():
            for fpath in files:
                try:
                    content = open(fpath, "r", encoding="utf-8").read()
                    # 截取前3000字符, 避免上下文过长
                    snippet = content[:3000]
                    if len(content) > 3000:
                        snippet += "\n... (文件过长, 已截断)"
                    code_snippets.append(f"### {os.path.basename(fpath)} ({role})\n```\n{snippet}\n```")
                except Exception:
                    pass
        if code_snippets:
            tester_context = (
                "\n\n【已生成的实际代码 - 请针对这些代码编写测试】\n"
                + "\n\n".join(code_snippets) +
                "\n\n请仔细阅读上述代码, 编写针对实际API签名和页面结构的测试用例。"
                "如果可能, 请运行 python -m pytest 验证测试通过。"
            )

    # 构建任务提示词
    prompt = (
        f"你是{role_name}。请完成以下开发任务：\n\n"
        f"【任务】{task_description}\n"
        f"【需求】{feature}\n"
        f"{extra_context}\n"
        f"要求：\n"
        f"1. 将生成的完整代码文件保存到 {role_dir} 目录\n"
        f"2. 代码要完整、可直接运行、不要省略任何部分\n"
        f"3. 在代码中适当添加注释\n"
        f"4. 完成后用1-2句话总结你生成了什么文件\n"
        f"{board_section}"
        f"{tester_context}"
        f"\n请开始工作。"
    )

    def _run():
        event_bus.publish("log", {
            "ai_id": role_id,
            "ai_name": role_name,
            "message": f"开始执行: {task_description[:50]}..."
        })

        event_bus.publish("ai_status", {
            "ai_id": role_id,
            "ai_name": role_name,
            "status": "thinking",
            "current_task": {"description": task_description}
        })

        # 在公告板上发布开始消息 (Fix 1)
        board.post(role_id, role_name,
                   f"开始工作: {task_description[:80]}\n"
                   f"工作目录: {role_dir}")

        try:
            event_bus.publish("ai_status", {
                "ai_id": role_id,
                "ai_name": role_name,
                "status": "coding",
                "current_task": {"description": task_description}
            })

            # 模块5: 加载记忆上下文
            memory_mgr = get_memory_manager(role_id)
            memory_context = memory_mgr.load_context()
            memory_mgr.remember(f"开始执行任务: {task_description[:80]}", "任务系统")

            # 使用统一 LLM Client 流式调用 Claude
            result = llm_client.chat_stream(
                prompt=prompt,
                system_prompt=system_prompt,
                allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
                cwd=role_dir,
                timeout=300,
                memory_context=memory_context,
                on_line=lambda line: event_bus.publish("worker_output", {
                    "ai_id": role_id,
                    "ai_name": role_name,
                    "line": line[:200]
                }),
                on_error=lambda err: (
                    event_bus.publish("log", {
                        "ai_id": role_id,
                        "ai_name": role_name,
                        "message": f"执行异常: {err}"
                    }),
                    memory_mgr.remember(f"执行错误: {err}", "系统", mtype="error")
                )
            )

            new_files = _detect_new_files(role_dir)

            if result["success"]:
                status = "done"
                msg = f"任务完成! 产出: {', '.join(new_files) if new_files else '无新文件'}"
            else:
                status = "error"
                msg = f"执行异常: {result.get('error', '未知错误')[:100]}"

            # 模块5: 任务完成, 归档记忆
            memory_mgr.remember(f"任务结果: {msg}", "任务系统", mtype="info" if status == "done" else "error")
            memory_mgr.complete_task(task_summary=f"{task_description[:60]} → {msg}")

            event_bus.publish("ai_status", {
                "ai_id": role_id,
                "ai_name": role_name,
                "status": status,
                "current_task": None
            })

            event_bus.publish("log", {
                "ai_id": role_id,
                "ai_name": role_name,
                "message": msg
            })

            # 在公告板上发布完成消息 (Fix 1)
            board.post(role_id, role_name,
                       f"工作完成! {msg}\n"
                       f"产出文件: {', '.join(new_files) if new_files else '无'}")

            event_bus.publish("worker_done", {
                "ai_id": role_id,
                "task_id": task_id,
                "status": status,
                "files": new_files,
                "role": role_id
            })

        except Exception as e:
            event_bus.publish("ai_status", {
                "ai_id": role_id, "ai_name": role_name,
                "status": "error", "current_task": None
            })
            event_bus.publish("log", {
                "ai_id": role_id, "ai_name": role_name,
                "message": f"执行异常: {str(e)}"
            })

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


def _detect_new_files(role_dir: str) -> list[str]:
    """检测目录中的代码文件 (排除系统文件)"""
    if not os.path.exists(role_dir):
        return []
    files = []
    for f in os.listdir(role_dir):
        if f.startswith("_") or f.endswith(".tmp") or f.endswith(".ps1") or f.endswith(".lock"):
            continue
        fpath = os.path.join(role_dir, f)
        if os.path.isfile(fpath):
            files.append(f)
    return files
