/**
 * 多Claude协同系统 Demo - 前端逻辑
 * SSE实时通信, 终端状态更新, 对话, 任务管理, 代码预览
 */

// ===== 系统状态 =====
let aiStatuses = {};
let taskData = [];

// ===== 初始化 =====
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initSSE();
    fetchStatus();
});

// ===== Tab切换 =====
function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;

            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            const tabEl = document.getElementById('tab-' + tabName);
            if (tabEl) tabEl.classList.add('active');

            // 切换到代码Tab时刷新文件树
            if (tabName === 'code') refreshFileTree();
        });
    });
}

// ===== SSE 实时连接 =====
function initSSE() {
    const es = new EventSource('/api/events');

    es.onmessage = function(event) {
        try {
            const msg = JSON.parse(event.data);
            handleEvent(msg.type, msg.data);
        } catch(e) {
            console.error('SSE解析错误:', e);
        }
    };

    es.onerror = function() {
        console.warn('SSE连接中断, 自动重连中...');
        document.getElementById('sysStatus').style.background = '#f85149';
        document.getElementById('sysStatusText').textContent = '重连中...';
    };

    es.onopen = function() {
        document.getElementById('sysStatus').style.background = '#3fb950';
        document.getElementById('sysStatusText').textContent = '系统运行中';
    };
}

// ===== 事件处理器 =====
function handleEvent(type, data) {
    switch(type) {
        case 'connected':
            addLog('system', 'SSE连接已建立, 开始接收实时数据');
            break;

        case 'log':
            addLog(data.ai_name, data.message);
            break;

        case 'ai_status':
            aiStatuses[data.ai_id] = data;
            renderAICards();
            break;

        case 'task_created':
            addLog('管理AI', `任务 [${data.task_id}] 已创建: ${data.description}`);
            fetchStatus();
            break;

        case 'subtask_created':
            addLog('管理AI', `子任务 [${data.task_id}] 已分配 → ${data.assigned_role}`);
            fetchStatus();
            break;

        case 'worker_output':
            // 实时显示Claude执行AI的输出
            addLog(data.ai_name, data.line);
            break;

        case 'worker_done':
            addLog(data.ai_name, `任务完成! 产出: ${(data.files || []).join(', ') || '无'}`);
            fetchStatus();
            if (data.files && data.files.length > 0) {
                showCodeNotification(data.files);
            }
            break;

        case 'subtask_done':
            addLog(data.ai_id, `子任务 [${data.task_id}] 已完成`);
            fetchStatus();
            if (data.result && data.result.files) {
                showCodeNotification(data.result.files);
            }
            break;

        case 'ready_for_approval':
            addLog('管理AI', `━━━ 任务 [${data.task_id}] 全部完成, 等待审批 ━━━`);
            fetchStatus();
            addChatMessage('manager', `任务「${data.description}」所有子任务已完成, 请前往【任务】面板审批。`);
            switchTab('tasks');
            // 加载审批摘要
            loadApprovalSummary(data.task_id);
            break;

        case 'task_approved':
            addLog('管理AI', `✓ 任务 [${data.task_id}] 已审批通过`);
            fetchStatus();
            break;

        case 'task_rejected':
            addLog('管理AI', `✗ 任务 [${data.task_id}] 已驳回: ${data.reason}`);
            fetchStatus();
            addChatMessage('manager', `任务 [${data.task_id}] 已被驳回, 原因: ${data.reason}。请与管理AI讨论修改方案。`);
            break;

        case 'project_delivered':
            addLog('管理AI', `📦 项目已交付 → ${data.project_dir}`);
            addChatMessage('manager', `项目「${data.project_name}」已汇总交付! 路径: ${data.project_dir}`);
            break;

        case 'board_post':
            addLog('公告板', `[${data.role_name}] ${data.message.substring(0, 80)}`);
            break;

        case 'system_reset':
            addLog('system', '系统已重置');
            aiStatuses = {};
            taskData = [];
            renderAICards();
            document.getElementById('taskList').innerHTML = '<div class="task-empty">暂无任务</div>';
            document.getElementById('fileTree').innerHTML = '<div class="file-tree-empty">暂无文件</div>';
            document.getElementById('codeViewer').innerHTML = '<div class="code-placeholder"><span class="code-icon">📄</span><p>选择左侧文件查看代码</p></div>';
            break;

        case 'heartbeat':
            // 心跳, 忽略
            break;
    }
}

// ===== 日志 =====
function addLog(source, message) {
    const stream = document.getElementById('logStream');
    const time = new Date().toLocaleTimeString('zh-CN', { hour12: false });

    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `
        <span class="log-time">${time}</span>
        <span class="log-ai">[${source}]</span>
        <span class="log-msg">${escapeHtml(message)}</span>
    `;

    stream.appendChild(entry);
    stream.scrollTop = stream.scrollHeight;

    // 限制日志数量
    while (stream.children.length > 200) {
        stream.removeChild(stream.firstChild);
    }
}

function clearLogs() {
    const stream = document.getElementById('logStream');
    stream.innerHTML = '';
    addLog('system', '日志已清空');
}

// ===== AI状态卡片 =====
function renderAICards() {
    const container = document.getElementById('aiCards');

    // 合并初始状态
    const cards = [
        {
            id: 'manager', name: '管理AI', role: '团队管理者', icon: '⚙',
            status: aiStatuses['manager']?.status || 'idle',
            cssClass: 'manager'
        },
        {
            id: 'frontend_dev', name: '前端开发AI', role: '前端工程师', icon: '🎨',
            status: aiStatuses['frontend_dev']?.status || 'idle',
            current_task: aiStatuses['frontend_dev']?.current_task,
            cssClass: 'frontend'
        },
        {
            id: 'backend_dev', name: '后端开发AI', role: '后端工程师', icon: '🗄',
            status: aiStatuses['backend_dev']?.status || 'idle',
            current_task: aiStatuses['backend_dev']?.current_task,
            cssClass: 'backend'
        },
        {
            id: 'tester', name: '测试AI', role: '测试工程师', icon: '🧪',
            status: aiStatuses['tester']?.status || 'idle',
            current_task: aiStatuses['tester']?.current_task,
            cssClass: 'tester'
        }
    ];

    const statusLabels = {
        idle: '空闲', thinking: '思考中...', coding: '编码中...',
        assigning: '分配中...', monitoring: '监控中...',
        done: '完成', error: '出错'
    };

    container.innerHTML = cards.map(c => `
        <div class="ai-card ${c.cssClass}">
            <span class="ai-icon">${c.icon}</span>
            <div class="ai-info">
                <div class="ai-name">${c.name}</div>
                <div class="ai-role">${c.role}${c.current_task ? ' • 任务: ' + c.current_task.description.substring(0, 20) + '...' : ''}</div>
            </div>
            <div class="ai-status-indicator">
                <span class="status-light ${c.status}"></span>
                <span>${statusLabels[c.status] || c.status}</span>
            </div>
        </div>
    `).join('');
}

// ===== 对话 =====
function sendChat() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message) return;

    // 显示人类消息
    addChatMessage('human', message);
    input.value = '';

    // 显示"思考中"占位
    const thinkingId = 'thinking-' + Date.now();
    addChatMessage('manager', '思考中...', thinkingId);

    // 发送到后端
    fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message })
    })
    .then(r => r.json())
    .then(data => {
        // 移除"思考中"占位
        removeChatMessage(thinkingId);

        if (data.code === 200) {
            // 显示管理AI的真实回复
            if (data.reply) {
                addChatMessage('manager', data.reply);
            }

            // 如果有任务拆解, 显示提示
            if (data.delegation) {
                const count = data.delegation.task_count;
                addChatMessage('manager',
                    `已拆解为 ${count} 个子任务, 正在启动执行AI终端窗口...`);
                // 触发任务列表刷新
                setTimeout(fetchStatus, 2000);
            }
        } else {
            addChatMessage('manager', '抱歉, 系统错误: ' + (data.reply || '未知错误'));
        }
    })
    .catch(err => {
        removeChatMessage(thinkingId);
        addChatMessage('manager', '抱歉, 系统出现错误: ' + err.message);
    });
}

function addChatMessage(sender, text, msgId) {
    const container = document.getElementById('chatMessages');
    const msg = document.createElement('div');
    msg.className = 'chat-msg ' + (sender === 'human' ? 'human' : 'manager');
    if (msgId) msg.id = msgId;

    if (sender === 'manager') {
        msg.innerHTML = `<div class="msg-sender">🤖 管理AI</div><div class="msg-body">${escapeHtml(text)}</div>`;
    } else {
        msg.innerHTML = `<div class="msg-sender">👤 你</div><div class="msg-body">${escapeHtml(text)}</div>`;
    }

    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
}

function removeChatMessage(msgId) {
    const el = document.getElementById(msgId);
    if (el) el.remove();
}

function quickTask(text) {
    document.getElementById('chatInput').value = text;
    sendChat();
}

// ===== 任务 =====
function renderTasks() {
    const container = document.getElementById('taskList');

    if (taskData.length === 0) {
        container.innerHTML = '<div class="task-empty">暂无任务, 请在对话中提交需求</div>';
        return;
    }

    const statusLabels = {
        pending: '待处理',
        assigned: '已分配',
        in_progress: '进行中',
        pending_approval: '⚠ 待审批',
        approved: '✓ 已批准',
        done: '已完成'
    };

    // 只显示顶层任务 (没有 parent_id 的)
    const topTasks = taskData.filter(t => !t.parent_id);
    const subTasks = taskData.filter(t => t.parent_id);

    container.innerHTML = topTasks.map(task => {
        const children = subTasks.filter(s => s.parent_id === task.id);
        const roleNames = {
            frontend_dev: '前端开发AI', backend_dev: '后端开发AI', tester: '测试AI'
        };

        let subtaskHtml = '';
        if (children.length > 0) {
            subtaskHtml = `
                <div class="subtask-list">
                    ${children.map(st => `
                        <div class="subtask-item">
                            <span class="subtask-dot ${st.status}"></span>
                            <span>${roleNames[st.assigned_role] || st.assigned_role}: ${escapeHtml(st.description)}</span>
                            <span style="font-size:10px;color:var(--text-muted)">[${statusLabels[st.status] || st.status}]</span>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        const badgeClass = task.status === 'pending_approval' ? 'badge-pending_approval' :
                           task.status === 'approved' ? 'badge-approved' :
                           task.status === 'rejected' ? 'badge-pending' :
                           task.status === 'done' ? 'badge-done' :
                           'badge-in_progress';

        let actionHtml = '';
        if (task.status === 'pending_approval') {
            actionHtml = `
                <div class="approval-panel">
                    <div class="approval-summary" id="approval-summary-${task.id}">
                        <p style="color:var(--text-muted);font-size:12px;">加载审批摘要中...</p>
                    </div>
                    <div style="display:flex;gap:10px;margin-top:10px;">
                        <button class="btn-approve" onclick="approveTask('${task.id}')">✓ 审批通过</button>
                        <button class="btn-reject" onclick="showRejectDialog('${task.id}')">✗ 驳回修改</button>
                    </div>
                </div>`;
        } else if (task.status === 'approved' && task.result) {
            actionHtml = `<div style="color:var(--accent-green);font-size:12px;margin-top:8px;">📦 项目已交付: ${escapeHtml(task.result.project_dir || '')}</div>`;
        } else if (task.status === 'rejected') {
            actionHtml = `<div style="color:var(--accent-red);font-size:12px;margin-top:8px;">⚠ 已驳回: ${escapeHtml(task.reject_reason || '')}</div>`;
        }

        return `
            <div class="task-card">
                <div class="task-card-header">
                    <span class="task-card-title">📋 ${escapeHtml(task.description)}</span>
                    <span class="task-badge ${badgeClass}">${statusLabels[task.status] || task.status}</span>
                </div>
                ${subtaskHtml}
                ${actionHtml}
            </div>
        `;
    }).join('');
}

function loadApprovalSummary(taskId) {
    // 加载公告板内容作为审批参考
    fetch('/api/board')
        .then(r => r.json())
        .then(data => {
            const el = document.getElementById('approval-summary-' + taskId);
            if (!el) return;
            const conflicts = data.data.conflicts || [];
            let html = '';
            if (conflicts.length > 0) {
                html += '<div style="color:var(--accent-yellow);font-size:12px;">⚠ 发现 ' + conflicts.length + ' 个潜在问题:</div>';
                conflicts.forEach(c => {
                    html += `<div style="color:var(--accent-yellow);font-size:11px;margin-left:8px;">• [${c.type}] ${c.message}</div>`;
                });
            } else {
                html += '<div style="color:var(--accent-green);font-size:12px;">✓ 未检测到冲突</div>';
            }
            html += '<div style="color:var(--text-muted);font-size:11px;margin-top:4px;">请审查代码后批准或驳回</div>';
            el.innerHTML = html;
        });
}

function approveTask(taskId) {
    fetch('/api/task/' + taskId + '/approve', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            addLog('人类', `已审批通过任务 [${taskId}]`);
            fetchStatus();
            if (data.data && data.data.project_dir) {
                addChatMessage('manager', `任务 [${taskId}] 已审批通过! 项目已交付到: ${data.data.project_dir}`);
            } else {
                addChatMessage('manager', `任务 [${taskId}] 已审批通过! 工作流程完成 ✓`);
            }
        });
}

function showRejectDialog(taskId) {
    const reason = prompt('请输入驳回原因:');
    if (!reason) return;
    fetch('/api/task/' + taskId + '/reject', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: reason })
    })
        .then(r => r.json())
        .then(data => {
            addLog('人类', `已驳回任务 [${taskId}]: ${reason}`);
            fetchStatus();
        });
}
        });
}

// ===== 代码预览 =====
function refreshFileTree() {
    fetch('/api/workspace/tree')
        .then(r => r.json())
        .then(data => {
            const container = document.getElementById('fileTree');
            if (!data.data || data.data.length === 0) {
                container.innerHTML = '<div class="file-tree-empty">暂无文件</div>';
                return;
            }

            const roleIcons = { frontend: '🎨', backend: '🗄', tests: '🧪' };

            container.innerHTML = data.data.map(group => `
                <div class="file-tree-group">
                    <div class="file-tree-group-title">${roleIcons[group.role] || '📁'} ${group.role_name}</div>
                    ${group.files.map(f => `
                        <div class="file-tree-item" onclick="viewFile('${f.path}')" data-path="${f.path}">
                            📄 ${f.name}
                        </div>
                    `).join('')}
                </div>
            `).join('');
        });
}

function viewFile(filepath) {
    // 高亮选中项
    document.querySelectorAll('.file-tree-item').forEach(el => el.classList.remove('active'));
    const item = document.querySelector(`[data-path="${filepath}"]`);
    if (item) item.classList.add('active');

    // 加载文件内容
    fetch('/api/workspace/file?path=' + encodeURIComponent(filepath))
        .then(r => r.json())
        .then(data => {
            const viewer = document.getElementById('codeViewer');
            if (data.code === 200 && data.data) {
                const ext = filepath.split('.').pop();
                const langMap = { html: 'HTML', css: 'CSS', js: 'JavaScript', py: 'Python' };

                const lines = data.data.content.split('\n');
                viewer.innerHTML = `
                    <div class="code-header">
                        <span class="code-filename">📄 ${filepath}</span>
                        <span class="code-lang">${langMap[ext] || ext}</span>
                    </div>
                    <div class="code-content">
                        ${lines.map(line => `<span class="line">${escapeHtml(line)}</span>`).join('\n')}
                    </div>
                `;
            } else {
                viewer.innerHTML = '<div class="code-placeholder"><p>文件读取失败</p></div>';
            }
        })
        .catch(() => {
            document.getElementById('codeViewer').innerHTML =
                '<div class="code-placeholder"><p>文件加载失败</p></div>';
        });
}

function showCodeNotification(files) {
    // 在日志中提示可查看代码
    addLog('system', `💡 新代码已生成: ${files.join(', ')}, 可在【代码】面板查看`);
}

// ===== 工具函数 =====
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    const btn = document.querySelector(`[data-tab="${tabName}"]`);
    if (btn) btn.classList.add('active');

    const tabEl = document.getElementById('tab-' + tabName);
    if (tabEl) tabEl.classList.add('active');

    if (tabName === 'code') refreshFileTree();
    if (tabName === 'tasks') fetchStatus();
}

function resetSystem() {
    if (!confirm('确定要重置系统吗? 这将清空所有任务和工作区文件。')) return;
    fetch('/api/reset', { method: 'POST' })
        .then(r => r.json())
        .then(() => {
            addLog('system', '系统已重置');
            document.getElementById('chatMessages').innerHTML = `
                <div class="chat-msg manager">
                    <div class="msg-sender">🤖 管理AI</div>
                    <div class="msg-body">系统已重置。你好! 我是管理AI, 请提交你的开发需求。</div>
                </div>
            `;
        });
}

// ===== 初始加载 =====
function fetchStatus() {
    fetch('/api/status')
        .then(r => r.json())
        .then(data => {
            if (data.ai_list) {
                data.ai_list.forEach(ai => {
                    aiStatuses[ai.id] = ai;
                });
                renderAICards();
            }
            if (data.tasks) {
                taskData = data.tasks;
                renderTasks();
            }
        })
        .catch(err => console.error('获取状态失败:', err));
}

renderAICards();
