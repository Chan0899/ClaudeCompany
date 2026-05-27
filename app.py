"""
多Claude协同系统 Demo - Flask主应用
四层架构: 人类负责人(UI) → 管理AI → 执行AI集群 → 代码工作区
"""
import sys
import io
# Windows下强制UTF-8输出, 避免GBK编码报错
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import os
import json
import time
from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS

from config import HOST, PORT, DEBUG, AI_ROLES, WORKSPACE_DIR, AI_MODE
from core.event_bus import event_bus
from core.workspace import workspace
from core.task_manager import task_manager
from core.manager_ai import ManagerAI
from core.manager_chat import manager_chat
from core.background_worker import run_claude_worker
from core.bulletin_board import board
from core.persistence import persistence
from roles.frontend_dev import FrontendDevAI
from roles.backend_dev import BackendDevAI
from roles.tester import TesterAI

# ============================================================
# 初始化 Flask 应用
# ============================================================
app = Flask(__name__)
CORS(app)

# ============================================================
# 初始化所有AI实例
# ============================================================
print("=" * 60)
print("  多Claude协同系统 Demo 启动中...")
print(f"  运行模式: {AI_MODE}")
print("=" * 60)

# 创建执行AI集群 (simulated模式下使用, claude模式下作为备用)
frontend_ai = FrontendDevAI("frontend_dev", "前端开发AI", "前端工程师")
backend_ai = BackendDevAI("backend_dev", "后端开发AI", "后端工程师")
tester_ai = TesterAI("tester", "测试AI", "测试工程师")

executor_pool = {
    "frontend_dev": frontend_ai,
    "backend_dev": backend_ai,
    "tester": tester_ai
}

# 创建管理AI (注入执行AI池)
manager_ai = ManagerAI(executor_pool)

# 角色名称映射 (多处使用)
ROLE_NAME_MAP = {
    "frontend_dev": "前端开发AI",
    "backend_dev": "后端开发AI",
    "tester": "测试AI",
}
ROLE_DIR_MAP = {
    "frontend_dev": "frontend",
    "backend_dev": "backend",
    "tester": "tests",
}

print("✓ 管理AI 已就绪 (Claude对话模式)")
print("✓ 后台执行器 已就绪 (Claude静默运行, 输出流到网页)")
print("✓ 公告板已就绪 (AI间通信)")
print("=" * 60)

# 恢复上次会话状态
_chat_hist = persistence.load("chat_history")
if _chat_hist:
    manager_chat.history = _chat_hist
    print(f"✓ 已恢复对话历史 ({len(_chat_hist)} 条)")

# 阶段感知: 存储等待依赖完成后再启动的任务
# {parent_id: [{task_dict, ...}, ...]}
_pending_dependent_tasks: dict[str, list] = {}
# 跟踪每个parent_id下已完成依赖的角色
_completed_roles: dict[str, set] = {}


def _save_chat_history():
    """持久化对话历史"""
    persistence.save("chat_history", manager_chat.history)


def _save_tasks():
    """持久化任务状态"""
    persistence.save("tasks", task_manager.get_all_tasks())


# 后台监听: 执行AI完成事件 → 更新任务状态 → 启动依赖任务 → 审批检查
def _on_worker_done_callback():
    """监听 worker_done 事件, 处理任务完成和依赖链"""
    import threading
    q = event_bus.subscribe()
    def _listen():
        while True:
            try:
                msg = q.get(timeout=1)
                data = json.loads(msg)
                if data["type"] == "worker_done":
                    wdata = data["data"]
                    role = wdata["role"]
                    # 更新对应子任务状态为 done
                    for tid, task in list(task_manager.tasks.items()):
                        if (task.assigned_role == role and
                            task.status not in ("done", "approved", "rejected")):
                            task_manager.update_status(tid, "done", {
                                "files": wdata.get("files", []),
                                "role": role
                            })
                            parent_id = task.parent_id
                            break
                    else:
                        continue

                    if not parent_id:
                        continue

                    # 跟踪已完成角色
                    if parent_id not in _completed_roles:
                        _completed_roles[parent_id] = set()
                    _completed_roles[parent_id].add(role)

                    # 检查是否有等待此依赖的任务
                    pending = _pending_dependent_tasks.get(parent_id, [])
                    still_pending = []
                    for ptask in pending:
                        deps = ptask.get("depends_on", [])
                        if all(d in _completed_roles.get(parent_id, set()) for d in deps):
                            # 所有依赖已满足, 启动此任务
                            _launch_single_worker(ptask, parent_id)
                            event_bus.publish("log", {
                                "ai_id": "manager", "ai_name": "管理AI",
                                "message": f"依赖满足, 启动 {ROLE_NAME_MAP.get(ptask['role'], ptask['role'])} (等待了 {', '.join(deps)})"
                            })
                        else:
                            still_pending.append(ptask)
                    _pending_dependent_tasks[parent_id] = still_pending

                    # 检查父任务是否所有子任务都完成
                    if task.parent_id:
                        task_manager._check_parent_completion(task)

                    # 持久化
                    _save_tasks()
            except Exception:
                pass
    t = threading.Thread(target=_listen, daemon=True)
    t.start()

_on_worker_done_callback()


# ============================================================
# API路由
# ============================================================

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')


@app.route('/api/status')
def get_status():
    """获取所有AI状态 + 任务列表"""
    all_ai = []

    # 管理AI
    all_ai.append({
        "id": manager_ai.ai_id,
        "name": manager_ai.name,
        "role": manager_ai.role,
        "status": manager_ai.status,
        "icon": AI_ROLES["manager"]["icon"]
    })

    # 执行AI集群
    for ai in executor_pool.values():
        all_ai.append({
            "id": ai.ai_id,
            "name": ai.name,
            "role": ai.role,
            "status": ai.status,
            "current_task": ai.current_task,
            "icon": AI_ROLES[ai.ai_id]["icon"]
        })

    return jsonify({
        "ai_list": all_ai,
        "tasks": task_manager.get_all_tasks()
    })


@app.route('/api/chat', methods=['POST'])
def send_chat():
    """
    人类向管理AI发送消息 (真实Claude对话)
    Body: {"message": "创建一个登录页面"}

    管理AI通过 claude -p 进行智能回复。
    如果回复中包含任务拆解(<<<DELEGATE>>>), 自动启动执行AI终端。
    """
    data = request.get_json()
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"code": 400, "message": "消息不能为空"}), 400

    # 更新管理AI状态
    manager_ai._set_status("thinking")
    event_bus.publish("log", {
        "ai_id": "manager",
        "ai_name": "管理AI",
        "message": f"收到消息: {message[:50]}..."
    })

    # 调用真实Claude进行管理AI对话
    result = manager_chat.chat(message)
    _save_chat_history()

    # 更新状态
    if result["delegation"]:
        manager_ai._set_status("assigning")
    else:
        manager_ai._set_status("idle")

    # 如果有任务拆解, 启动执行AI
    if result["delegation"]:
        tasks = result["delegation"]["tasks"]
        _spawn_workers(message, tasks)
        return jsonify({
            "code": 200,
            "reply": result["reply"],
            "delegation": {"task_count": len(tasks), "tasks": tasks},
            "data": {"requirement": message}
        })
    elif result["error"]:
        return jsonify({
            "code": 500,
            "reply": result["reply"],
            "error": result["error"]
        }), 500
    else:
        return jsonify({
            "code": 200,
            "reply": result["reply"],
            "delegation": None,
            "data": {"requirement": message}
        })


def _launch_single_worker(task: dict, parent_id: str, extra_context: str = ""):
    """启动单个后台Claude worker (创建子任务 + 启动进程)"""
    role_id = task["role"]
    description = task["description"]
    role_name = ROLE_NAME_MAP.get(role_id, role_id)
    workspace_subdir = ROLE_DIR_MAP.get(role_id, role_id)
    deps = task.get("depends_on", [])

    # 创建子任务 (带依赖信息)
    subtask = task_manager.create_subtask(
        description=description,
        assigned_role=role_id,
        parent_id=parent_id,
        depends_on=deps
    )

    event_bus.publish("log", {
        "ai_id": "manager",
        "ai_name": "管理AI",
        "message": f"派活 [{subtask.id}] → {role_name}: {description[:50]}..."
    })

    # 后台启动Claude
    run_claude_worker(
        role_id=role_id,
        role_name=role_name,
        workspace_subdir=workspace_subdir,
        task_description=description,
        feature=f"任务ID:{subtask.id}",
        task_id=subtask.id,
        extra_context=extra_context
    )


def _spawn_workers(feature: str, tasks: list[dict]):
    """阶段感知的任务派发 (Fix 2: 依赖排序)"""
    import threading

    def _launch():
        try:
            parent_id = task_manager.create_task(feature).id
            manager_ai._set_status("assigning")
            _completed_roles[parent_id] = set()

            # 清空工作区 (旧任务残留), 新项目从零开始
            for subdir in ["frontend", "backend", "tests"]:
                d = os.path.join(WORKSPACE_DIR, subdir)
                if os.path.exists(d):
                    for f in os.listdir(d):
                        if not f.startswith("_"):
                            os.remove(os.path.join(d, f))
            event_bus.publish("log", {
                "ai_id": "manager", "ai_name": "管理AI",
                "message": "工作区已清空, 开始新项目"
            })

            # 管理AI发公告
            board.post("manager", "管理AI",
                       f"新任务启动: {feature}\n"
                       f"参与角色: {', '.join(ROLE_NAME_MAP.get(t['role'], t['role']) for t in tasks)}")

            # 清理公告板旧内容, 开始新项目
            board.clear()
            board.post("manager", "管理AI", f"=== 新项目: {feature} ===\n请各AI在下方留言协调工作")

            # Phase 1: 无依赖的任务立即启动
            phase1 = [t for t in tasks if not t.get("depends_on")]
            phase2 = [t for t in tasks if t.get("depends_on")]

            if not phase1 and phase2:
                phase1 = phase2
                phase2 = []

            for task in phase1:
                _launch_single_worker(task, parent_id)

            # Phase 2: 存储依赖任务, 等待依赖完成
            if phase2:
                _pending_dependent_tasks[parent_id] = phase2
                for ptask in phase2:
                    deps = ptask.get("depends_on", [])
                    event_bus.publish("log", {
                        "ai_id": "manager", "ai_name": "管理AI",
                        "message": f"待启动: {ROLE_NAME_MAP.get(ptask['role'], ptask['role'])} (依赖: {', '.join(deps)})"
                    })

            manager_ai._set_status("monitoring")
            phase_info = f"Phase1: {len(phase1)}个, Phase2: {len(phase2)}个"
            event_bus.publish("log", {
                "ai_id": "manager", "ai_name": "管理AI",
                "message": f"任务派发完成 ({phase_info}), 监控中..."
            })

            _save_tasks()
        except Exception as e:
            event_bus.publish("log", {
                "ai_id": "manager", "ai_name": "管理AI",
                "message": f"派活失败: {str(e)}"
            })
            manager_ai._set_status("error")

    t = threading.Thread(target=_launch, daemon=True)
    t.start()


@app.route('/api/chat/history')
def chat_history():
    """获取管理AI对话历史"""
    return jsonify({
        "code": 200,
        "data": manager_chat.get_history()
    })


@app.route('/api/chat/reset', methods=['POST'])
def reset_chat():
    """重置管理AI对话历史"""
    manager_chat.reset()
    return jsonify({"code": 200, "message": "对话历史已重置"})


@app.route('/api/task/<task_id>/approve', methods=['POST'])
def approve_task(task_id):
    """人类审批通过任务 → 汇总项目 → 交付"""
    task = task_manager.tasks.get(task_id)
    if not task:
        return jsonify({"code": 404, "message": "任务不存在"}), 404

    # 冲突检测 (Fix 6)
    conflicts = board.detect_conflicts()
    if conflicts:
        event_bus.publish("log", {
            "ai_id": "manager", "ai_name": "管理AI",
            "message": f"冲突检测: 发现 {len(conflicts)} 个潜在问题"
        })
        for c in conflicts:
            event_bus.publish("log", {
                "ai_id": "manager", "ai_name": "管理AI",
                "message": f"  ⚠ [{c['type']}] {c['message']}"
            })

    task_manager.approve_task(task_id)
    manager_ai._log(f"任务 [{task_id}] 已通过人类审批 ✓")

    # 项目汇总 (Fix 5)
    project_name = task.description[:30].replace(" ", "_").replace("/", "_")
    project_dir = workspace.aggregate_project(project_name)

    event_bus.publish("log", {
        "ai_id": "manager", "ai_name": "管理AI",
        "message": f"项目已交付 → {project_dir}"
    })

    event_bus.publish("project_delivered", {
        "task_id": task_id,
        "project_name": project_name,
        "project_dir": project_dir
    })

    _save_tasks()

    return jsonify({
        "code": 200,
        "message": f"任务 [{task_id}] 已审批通过, 项目已交付",
        "data": {
            "project_dir": project_dir,
            "project_name": project_name,
            "conflicts": conflicts
        }
    })


@app.route('/api/task/<task_id>/reject', methods=['POST'])
def reject_task(task_id):
    """人类驳回任务 (带原因), 返回给管理AI重新处理"""
    task = task_manager.tasks.get(task_id)
    if not task:
        return jsonify({"code": 404, "message": "任务不存在"}), 404

    data = request.get_json() or {}
    reason = data.get("reason", "未说明原因")

    task_manager.reject_task(task_id, reason)
    manager_ai._log(f"任务 [{task_id}] 被驳回: {reason}")

    # 通知管理AI处理驳回
    event_bus.publish("log", {
        "ai_id": "manager", "ai_name": "管理AI",
        "message": f"⚠ 任务 [{task_id}] 被驳回! 原因: {reason}"
    })

    _save_tasks()

    return jsonify({
        "code": 200,
        "message": f"任务 [{task_id}] 已驳回",
        "data": {"reason": reason}
    })


@app.route('/api/board')
def get_board():
    """获取公告板内容 (AI间通信)"""
    content = board.read()
    conflicts = board.detect_conflicts()
    return jsonify({
        "code": 200,
        "data": {
            "content": content,
            "conflicts": conflicts
        }
    })


@app.route('/api/workspace/tree')
def get_workspace_tree():
    """获取工作区文件树"""
    tree = workspace.list_files()
    return jsonify({"code": 200, "data": tree})


@app.route('/api/workspace/file')
def get_workspace_file():
    """读取工作区文件内容 ?path=frontend/login.html"""
    filepath = request.args.get("path", "")
    if not filepath or "/" not in filepath:
        return jsonify({"code": 400, "message": "路径格式错误, 需为 role/filename"}), 400

    parts = filepath.split("/", 1)
    role, filename = parts[0], parts[1]

    content = workspace.read_file(role, filename)
    if not content:
        return jsonify({"code": 404, "message": "文件不存在"}), 404

    return jsonify({"code": 200, "data": {"path": filepath, "content": content}})


@app.route('/api/reset', methods=['POST'])
def reset_system():
    """重置系统: 清空工作区、任务、对话、公告板"""
    workspace.clear()
    task_manager.tasks.clear()
    task_manager.subtasks.clear()
    manager_chat.reset()
    board.clear()
    _pending_dependent_tasks.clear()
    _completed_roles.clear()
    for ai in executor_pool.values():
        ai.stop()
    manager_ai._processing = False
    manager_ai._set_status("idle")
    persistence.delete("chat_history")
    persistence.delete("tasks")

    event_bus.publish("system_reset", {"message": "系统已重置"})
    return jsonify({"code": 200, "message": "系统已重置"})


# ============================================================
# SSE (Server-Sent Events) - 实时推送
# ============================================================

@app.route('/api/events')
def sse_events():
    """SSE端点: 实时推送AI状态、日志、任务更新"""
    def generate():
        q = event_bus.subscribe()
        try:
            # 发送初始连接确认
            yield f"data: {json.dumps({'type': 'connected', 'data': {'message': 'SSE连接已建立'}}, ensure_ascii=False)}\n\n"

            while True:
                try:
                    msg = q.get(timeout=15)  # 15秒心跳间隔
                    yield f"data: {msg}\n\n"
                except Exception:
                    # 发送心跳保持连接
                    yield f"data: {json.dumps({'type': 'heartbeat', 'data': {}}, ensure_ascii=False)}\n\n"
        except GeneratorExit:
            event_bus.unsubscribe(q)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


# ============================================================
# 启动
# ============================================================

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print(f"  多Claude协同系统 Demo")
    print(f"  访问地址: http://{HOST}:{PORT}")
    print(f"  工作区目录: {WORKSPACE_DIR}")
    print("=" * 60 + "\n")
    app.run(host=HOST, port=PORT, debug=DEBUG, threaded=True)
