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
    initModalEvents();
});

// ===== Tab切换 =====
function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            switchTab(btn.dataset.tab);
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
    // 监控面板实时更新: 任务相关事件 → 刷新流水线+概览
    const monitorEvents = ['task_created', 'subtask_created', 'worker_done',
        'subtask_done', 'task_approved', 'task_rejected', 'task_stopped'];
    if (monitorEvents.includes(type)) {
        if (isMonitorActive()) {
            loadOverview();
            loadTaskPipeline();
        }
    }

    switch(type) {
        case 'connected':
            addLog('system', 'SSE连接已建立, 开始接收实时数据');
            break;

        case 'log':
            addLog(data.ai_name, data.message);
            // 检测错误关键词 → 实时刷新错误面板
            if (isMonitorActive()) {
                const msg = data.message || '';
                if (/error|Error|失败|错误|异常|超时/.test(msg)) {
                    loadErrors();
                }
            }
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
        <div class="ai-card ${c.cssClass}" onclick="openRoleModal('${c.id}')" title="点击查看角色详情">
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

    addChatMessage('human', message);
    input.value = '';

    const thinkingId = 'thinking-' + Date.now();
    addChatMessage('manager', '思考中...', thinkingId);

    fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message })
    })
    .then(r => r.json())
    .then(data => {
        removeChatMessage(thinkingId);

        if (data.code === 200) {
            if (data.reply) {
                addChatMessage('manager', data.reply);
            }

            if (data.delegation) {
                const count = data.delegation.task_count;
                addChatMessage('manager',
                    `已拆解为 ${count} 个子任务, 正在启动执行AI终端窗口...`);
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
    document.querySelectorAll('.file-tree-item').forEach(el => el.classList.remove('active'));
    const item = document.querySelector(`[data-path="${filepath}"]`);
    if (item) item.classList.add('active');

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
    addLog('system', `💡 新代码已生成: ${files.join(', ')}, 可在【代码】面板查看`);
}

// ===== 工具函数 =====
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function nowTime() {
    return new Date().toLocaleTimeString('zh-CN', { hour12: false });
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
    if (tabName === 'monitor') { loadOverview(); loadTaskPipeline(); loadErrors(); loadToolLogs(); }
}

function isMonitorActive() {
    const el = document.getElementById('tab-monitor');
    return el && el.classList.contains('active');
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

// ===== 监控面板 =====

const ROLE_ICONS = {
    manager: '⚙', frontend_dev: '🎨', backend_dev: '🗄', tester: '🧪'
};
const ROLE_DISPLAY = {
    manager: '管理AI', frontend_dev: '前端开发AI', backend_dev: '后端开发AI', tester: '测试AI'
};

function loadOverview() {
    fetch('/api/system/overview')
        .then(r => r.json())
        .then(data => {
            if (data.code !== 200) return;
            const db = data.data.database;
            const pipeline = data.data.task_pipeline || {};

            let activeTotal = 0, completedTotal = 0, errorTotal = 0;
            Object.values(pipeline).forEach(p => {
                activeTotal += (p.active || 0);
                completedTotal += (p.completed || 0);
                errorTotal += (p.errors || 0);
            });

            const cards = [
                { label: '活跃任务', value: activeTotal, accent: 'accent-blue' },
                { label: '已完成', value: completedTotal, accent: 'accent-green' },
                { label: '待审批', value: data.data.pending_approval_total || 0, accent: 'accent-purple' },
                { label: '错误', value: errorTotal + (db.total_errors || 0), accent: 'accent-red' },
                { label: '工具调用', value: db.total_tool_calls || 0, accent: '' },
                { label: '项目', value: db.total_projects || 0, accent: '' },
                { label: '模式', value: data.data.mode, accent: 'accent-blue' },
            ];
            document.getElementById('overviewStats').innerHTML = cards.map(c =>
                `<div class="metric-card ${c.accent}"><div class="metric-label">${c.label}</div><div class="metric-value">${c.value}</div></div>`
            ).join('');
        });
}

function loadTaskPipeline() {
    fetch('/api/system/overview')
        .then(r => r.json())
        .then(data => {
            if (data.code !== 200) return;
            const pipeline = data.data.task_pipeline || {};
            const panel = document.getElementById('taskPipelinePanel');
            const timeEl = document.getElementById('pipelineTime');
            if (timeEl) timeEl.textContent = nowTime();

            const roles = ['manager', 'frontend_dev', 'backend_dev', 'tester'];
            let html = '';

            const pendTotal = data.data.pending_approval_total || 0;
            const queue = data.data.queue_depth || 0;
            if (pendTotal > 0 || queue > 0) {
                html += '<div class="pipeline-summary">';
                if (pendTotal > 0) html += `⚠ 待审批: ${pendTotal} &nbsp;`;
                if (queue > 0) html += `⏳ 队列中: ${queue}`;
                html += '</div>';
            }

            html += roles.map(rid => {
                const p = pipeline[rid] || { active: 0, completed: 0, pending_approval: 0, errors: 0 };
                const hasActivity = p.active > 0 || p.completed > 0 || p.pending_approval > 0 || p.errors > 0;
                return `
                    <div class="pipeline-role">
                        <div class="pipeline-role-header">
                            <span>${ROLE_ICONS[rid] || '🤖'} ${ROLE_DISPLAY[rid] || rid}</span>
                        </div>
                        <div class="pipeline-badges">
                            <span class="pipeline-badge active">进行中: ${p.active}</span>
                            <span class="pipeline-badge completed">已完成: ${p.completed}</span>
                            ${p.pending_approval > 0 ? `<span class="pipeline-badge pending">待审批: ${p.pending_approval}</span>` : ''}
                            ${p.errors > 0 ? `<span class="pipeline-badge error">错误: ${p.errors}</span>` : ''}
                            ${!hasActivity ? '<span style="font-size:10px;color:var(--text-muted);">空闲</span>' : ''}
                        </div>
                    </div>`;
            }).join('');
            panel.innerHTML = html || '<div style="color:var(--text-muted);text-align:center;padding:20px;">暂无任务数据</div>';
        });
}

function loadErrors() {
    fetch('/api/errors?limit=20')
        .then(r => r.json())
        .then(data => {
            const panel = document.getElementById('errorsPanel');
            const timeEl = document.getElementById('errorsTime');
            if (timeEl) timeEl.textContent = nowTime();

            if (data.code === 200 && data.data.length > 0) {
                panel.innerHTML = data.data.map(e => {
                    const ts = e.created_at ? new Date(e.created_at * 1000).toLocaleString('zh-CN', { hour12: false }) : '';
                    return `
                        <div class="error-entry">
                            <span class="error-source">[${escapeHtml(e.source || '')}] ${escapeHtml(e.error_type || 'error')}</span>
                            <span class="error-time">${ts}</span>
                            <div class="error-msg">${escapeHtml((e.error_message || '').substring(0, 200))}</div>
                        </div>`;
                }).join('');
            } else {
                panel.innerHTML = '<div class="error-empty">✓ 暂无错误记录</div>';
            }
        });
}

function loadToolLogs() {
    fetch('/api/tool-logs?limit=30')
        .then(r => r.json())
        .then(data => {
            const panel = document.getElementById('toolLogsPanel');
            const timeEl = document.getElementById('toolsTime');
            if (timeEl) timeEl.textContent = nowTime();

            if (data.code === 200 && data.data.stats && data.data.stats.length > 0) {
                panel.innerHTML = data.data.stats.map(s => `
                    <div style="margin-bottom:4px;padding:6px;background:var(--bg-tertiary);border-radius:4px;font-size:10px;">
                        <span style="color:var(--accent-blue);font-weight:600;">${escapeHtml(s.tool_name)}</span>
                        <span style="color:var(--text-muted);margin-left:8px;">${s.call_count}次</span>
                        <span style="color:${s.success_rate>90?'var(--accent-green)':'var(--accent-yellow)'};margin-left:8px;">${s.success_rate}%</span>
                        <span style="color:var(--text-muted);margin-left:8px;">avg ${s.avg_ms}ms</span>
                    </div>
                `).join('');
            } else {
                panel.textContent = '暂无工具调用记录';
            }
        });
}

// ===== 角色详情弹窗 =====
let _modalRoleId = null;
let _modalRoleData = null;
let _modalMemoriesData = null;
let _allTools = null;  // 所有可用工具缓存

function initModalEvents() {
    const overlay = document.getElementById('modalOverlay');
    if (overlay) {
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) closeRoleModal();
        });
    }
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') closeRoleModal();
    });
    document.querySelectorAll('.modal-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchModalTab(btn.dataset.mtab));
    });
}

function openRoleModal(roleId) {
    _modalRoleId = roleId;
    _modalRoleData = null;
    _modalMemoriesData = null;

    document.getElementById('modalOverlay').classList.add('active');
    document.getElementById('modalTitle').innerHTML = `${ROLE_ICONS[roleId] || '🤖'} ${ROLE_DISPLAY[roleId] || roleId}`;

    document.querySelectorAll('.modal-tab-btn').forEach((b, i) => b.classList.toggle('active', i === 0));
    document.querySelectorAll('.modal-tab-content').forEach((c, i) => c.classList.toggle('active', i === 0));

    // 并行加载角色配置 + 工具列表 + 记忆
    fetch('/api/roles/' + encodeURIComponent(roleId))
        .then(r => r.json())
        .then(data => {
            if (data.code === 200) {
                _modalRoleData = data.data;
                renderModalHandbook(data.data);
            }
        });

    // 加载工具列表后渲染配置表单
    if (!_allTools) {
        fetch('/api/tools')
            .then(r => r.json())
            .then(data => {
                if (data.code === 200) _allTools = data.data;
                if (_modalRoleData) renderModalConfig(_modalRoleData);
            });
    }

    // 先加载角色配置, 再渲染 (等工具列表到位)
    fetch('/api/roles/' + encodeURIComponent(roleId))
        .then(r => r.json())
        .then(data => {
            if (data.code === 200) {
                _modalRoleData = data.data;
                if (_allTools) renderModalConfig(data.data);
            }
        });

    fetch('/api/memories/' + encodeURIComponent(roleId))
        .then(r => r.json())
        .then(data => {
            if (data.code === 200) {
                _modalMemoriesData = data.data;
                renderModalMemories(data.data);
            }
        });
}

function closeRoleModal() {
    document.getElementById('modalOverlay').classList.remove('active');
    _modalRoleId = null;
}

function switchModalTab(tabName) {
    document.querySelectorAll('.modal-tab-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.mtab === tabName);
    });
    document.querySelectorAll('.modal-tab-content').forEach(c => c.classList.remove('active'));
    const target = document.getElementById('modal-tab-' + tabName);
    if (target) target.classList.add('active');
}

// ===== 角色配置Tab (可编辑表单) =====

function renderModalConfig(data) {
    const container = document.getElementById('modal-tab-config');
    const perm = data.permissions || {};
    const crew = data.crewai_opts || {};
    const mem = data.memory_config || {};
    const roleTools = (data.tools || []).map(t => t.name);

    // 工具复选框
    let toolsHtml = '<div class="modal-tools-grid">';
    (_allTools || []).forEach(t => {
        const checked = roleTools.includes(t.name);
        toolsHtml += `
            <label class="modal-tool-checkbox-item ${checked ? 'checked' : ''}" onclick="this.querySelector('input').click()">
                <input type="checkbox" class="modal-checkbox" value="${escapeHtml(t.name)}"
                       data-tool-name="${escapeHtml(t.name)}" ${checked ? 'checked' : ''}
                       onchange="this.parentElement.classList.toggle('checked', this.checked)">
                <span>${escapeHtml(t.name)}</span>
                <span class="modal-tool-category">${escapeHtml(t.category || '')}</span>
            </label>`;
    });
    toolsHtml += '</div>';

    container.innerHTML = `
        <div class="modal-form-group">
            <div class="modal-form-label">名称</div>
            <div style="font-size:13px;color:var(--text-primary);padding:6px 0;">${escapeHtml(data.icon || '')} ${escapeHtml(data.name || '')} (${escapeHtml(data.title || '')})</div>
        </div>
        <div class="modal-form-group">
            <div class="modal-form-label">角色ID</div>
            <div style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);padding:4px 0;">${escapeHtml(data.role_id || '')}</div>
        </div>
        <div class="modal-form-group">
            <label class="modal-form-label" for="cfg-goal">工作目标</label>
            <textarea class="modal-textarea small" id="cfg-goal">${escapeHtml(data.goal || '')}</textarea>
        </div>
        <div class="modal-form-group">
            <div class="modal-form-label">绑定工具</div>
            ${toolsHtml}
        </div>
        <div class="modal-form-group">
            <div class="modal-form-label">权限</div>
            <label class="modal-checkbox-label"><input type="checkbox" class="modal-checkbox" id="cfg-can-delegate" ${perm.can_delegate ? 'checked' : ''}> 可委派</label>
            <label class="modal-checkbox-label"><input type="checkbox" class="modal-checkbox" id="cfg-can-approve" ${perm.can_approve ? 'checked' : ''}> 可审批</label>
            <label class="modal-checkbox-label"><input type="checkbox" class="modal-checkbox" id="cfg-can-access" ${perm.can_access_workspace ? 'checked' : ''}> 可访问工作区</label>
        </div>
        <div class="modal-form-group">
            <div class="modal-form-label">CrewAI参数</div>
            <label class="modal-checkbox-label" style="display:inline-block;width:100px;">max_iter</label>
            <input type="number" class="modal-input short" id="cfg-max-iter" value="${crew.max_iter || 10}" min="1" max="50">
            <label class="modal-checkbox-label" style="margin-left:12px;"><input type="checkbox" class="modal-checkbox" id="cfg-verbose" ${crew.verbose ? 'checked' : ''}> verbose</label>
            <label class="modal-checkbox-label"><input type="checkbox" class="modal-checkbox" id="cfg-allow-deleg" ${crew.allow_delegation ? 'checked' : ''}> allow_delegation</label>
        </div>
        <div class="modal-form-group">
            <div class="modal-form-label">记忆配置</div>
            <label class="modal-checkbox-label" style="display:inline-block;width:120px;">短期记忆上限</label>
            <input type="number" class="modal-input short" id="cfg-mem-max" value="${mem.short_term_max || 50}" min="10" max="200">
            <label class="modal-checkbox-label" style="margin-left:12px;"><input type="checkbox" class="modal-checkbox" id="cfg-mem-auto" ${mem.long_term_auto_save ? 'checked' : ''}> 自动存档</label>
        </div>
        <div class="modal-actions">
            <span class="modal-save-hint" id="cfgSaveHint">已保存 ✓</span>
            <button class="btn-save" onclick="saveRoleConfig()">💾 保存配置</button>
        </div>`;
}

function saveRoleConfig() {
    if (!_modalRoleId) return;

    // 收集工具
    const tools = [];
    document.querySelectorAll('#modal-tab-config input[data-tool-name]:checked').forEach(cb => {
        tools.push(cb.value);
    });

    const payload = {
        goal: document.getElementById('cfg-goal').value,
        tools: tools,
        permissions: {
            can_delegate: document.getElementById('cfg-can-delegate').checked,
            can_approve: document.getElementById('cfg-can-approve').checked,
            can_access_workspace: document.getElementById('cfg-can-access').checked,
        },
        crewai: {
            max_iter: parseInt(document.getElementById('cfg-max-iter').value) || 10,
            verbose: document.getElementById('cfg-verbose').checked,
            allow_delegation: document.getElementById('cfg-allow-deleg').checked,
        },
        memory: {
            short_term_max: parseInt(document.getElementById('cfg-mem-max').value) || 50,
            long_term_auto_save: document.getElementById('cfg-mem-auto').checked,
        },
    };

    fetch('/api/roles/' + encodeURIComponent(_modalRoleId) + '/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(r => r.json())
        .then(data => {
            const hint = document.getElementById('cfgSaveHint');
            if (data.code === 200) {
                hint.textContent = '已保存 ✓';
                hint.className = 'modal-save-hint show';
                setTimeout(() => hint.classList.remove('show'), 2000);
            } else {
                hint.textContent = '保存失败: ' + data.message;
                hint.style.color = 'var(--accent-red)';
                hint.className = 'modal-save-hint show';
            }
        });
}

// ===== 角色记忆Tab (可操作) =====

function renderModalMemories(data) {
    const container = document.getElementById('modal-tab-memories');

    // 短期记忆列表
    let shortHtml = '';
    if (data.short_term && data.short_term.length > 0) {
        shortHtml = '<div style="margin-bottom:6px;">';
        data.short_term.slice(-5).reverse().forEach((e, i) => {
            shortHtml += `<div style="padding:4px 8px;margin-bottom:2px;background:var(--bg-tertiary);border-radius:4px;font-size:11px;">
                <span style="color:var(--accent-yellow);">[${escapeHtml(e.type || 'info')}]</span>
                <span style="color:var(--text-muted);font-size:10px;margin-left:6px;">${escapeHtml(e.source || '')} ${e.ts ? new Date(e.ts*1000).toLocaleString('zh-CN',{hour12:false}) : ''}</span>
                <div style="color:var(--text-secondary);margin-top:1px;">${escapeHtml((e.content || '').substring(0, 150))}</div>
            </div>`;
        });
        shortHtml += '</div>';
    } else {
        shortHtml = '<div style="color:var(--text-muted);font-size:11px;margin-bottom:6px;">暂无短期记忆</div>';
    }

    container.innerHTML = `
        <div style="margin-bottom:8px;font-weight:600;font-size:12px;">
            短期记忆: ${data.short_count} 条 | 长期记忆: ${data.long_length} 字符
        </div>

        <!-- 添加短期记忆 -->
        <div class="modal-memory-add-row">
            <input type="text" class="modal-input" id="mem-new-content" placeholder="输入记忆内容..." style="flex:1;min-width:120px;">
            <select class="modal-select" id="mem-new-source">
                <option value="human">human</option>
                <option value="manager">manager</option>
                <option value="system">system</option>
            </select>
            <select class="modal-select" id="mem-new-type">
                <option value="info">info</option>
                <option value="decision">decision</option>
                <option value="error">error</option>
            </select>
            <button class="btn-add" onclick="addShortMemory()">+ 添加</button>
        </div>

        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
            <span style="font-size:11px;font-weight:600;color:var(--accent-blue);">📋 近期条目</span>
            ${data.short_count > 0 ? `<button class="btn-danger-sm" onclick="clearShortMemories()">清空</button>` : ''}
        </div>
        ${shortHtml}

        <!-- 长期记忆编辑 -->
        <div style="margin-top:8px;display:flex;flex-direction:column;flex:1;min-height:0;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                <span style="font-size:11px;font-weight:600;color:var(--accent-purple);">📝 长期记忆</span>
                <button class="btn-save" onclick="saveLongMemory()" style="font-size:11px;padding:4px 10px;">保存</button>
            </div>
            <textarea class="modal-textarea large" id="mem-long-text" style="flex:1;">${escapeHtml(data.long_term || '')}</textarea>
        </div>`;
}

function addShortMemory() {
    if (!_modalRoleId) return;
    const content = document.getElementById('mem-new-content').value.trim();
    if (!content) return;
    const source = document.getElementById('mem-new-source').value;
    const type = document.getElementById('mem-new-type').value;

    fetch('/api/memories/' + encodeURIComponent(_modalRoleId) + '/short-term', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, source, type })
    })
        .then(r => r.json())
        .then(() => {
            document.getElementById('mem-new-content').value = '';
            // 重新加载记忆
            fetch('/api/memories/' + encodeURIComponent(_modalRoleId))
                .then(r => r.json())
                .then(data => {
                    if (data.code === 200) renderModalMemories(data.data);
                });
        });
}

function clearShortMemories() {
    if (!_modalRoleId) return;
    if (!confirm('确定要清空该角色的所有短期记忆吗?')) return;
    fetch('/api/memories/' + encodeURIComponent(_modalRoleId) + '/short-term', { method: 'DELETE' })
        .then(r => r.json())
        .then(() => {
            fetch('/api/memories/' + encodeURIComponent(_modalRoleId))
                .then(r => r.json())
                .then(data => {
                    if (data.code === 200) renderModalMemories(data.data);
                });
        });
}

function saveLongMemory() {
    if (!_modalRoleId) return;
    const content = document.getElementById('mem-long-text').value;
    fetch('/api/memories/' + encodeURIComponent(_modalRoleId) + '/long-term', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content })
    })
        .then(r => r.json())
        .then(data => {
            if (data.code === 200) {
                // 临时显示保存成功
                showSaveHint('memSaveHint');
            }
        });
}

// ===== 人设手册Tab (编辑器) =====

function renderModalHandbook(data) {
    const container = document.getElementById('modal-tab-handbook');
    container.innerHTML = `
        <div style="display:flex;flex-direction:column;height:100%;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <span style="font-size:11px;color:var(--text-muted);">📖 claude.md 人设手册 (${data.claude_md_length || 0} 字符)</span>
                <span style="display:flex;align-items:center;gap:8px;">
                    <span class="modal-save-hint" id="hbSaveHint">已保存 ✓</span>
                    <button class="btn-save" onclick="saveRoleHandbook()" style="font-size:11px;padding:4px 10px;">💾 保存</button>
                </span>
            </div>
            <textarea class="modal-textarea" id="hb-content" style="flex:1;min-height:350px;">${escapeHtml(data.claude_md || '')}</textarea>
        </div>`;
}

function saveRoleHandbook() {
    if (!_modalRoleId) return;
    const content = document.getElementById('hb-content').value;
    fetch('/api/roles/' + encodeURIComponent(_modalRoleId) + '/handbook', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content })
    })
        .then(r => r.json())
        .then(data => {
            const hint = document.getElementById('hbSaveHint');
            if (data.code === 200) {
                hint.textContent = '已保存 ✓';
                hint.className = 'modal-save-hint show';
                setTimeout(() => hint.classList.remove('show'), 2000);
            } else {
                hint.textContent = '失败: ' + data.message;
                hint.style.color = 'var(--accent-red)';
                hint.className = 'modal-save-hint show';
            }
        });
}

function showSaveHint(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.add('show');
    setTimeout(() => el.classList.remove('show'), 2000);
}

renderAICards();
