"""
前端开发AI - 生成HTML/CSS/JS代码
"""
from core.executor_ai import ExecutorAI
from core.workspace import workspace


class FrontendDevAI(ExecutorAI):
    """前端工程师AI: 生成页面和组件代码"""

    def do_work(self, task: dict) -> dict:
        description = task.get("description", "")
        feature = task.get("feature", description)

        # 根据需求生成不同风格的前端代码
        filename = self._pick_filename(description)
        code = self._generate_code(feature, description)

        # 写入工作区
        filepath = workspace.write_file("frontend", filename, code)

        return {
            "files": [f"frontend/{filename}"],
            "filepath": filepath,
            "role": "frontend"
        }

    def _pick_filename(self, description: str) -> str:
        """根据需求选择合适的文件名"""
        desc = description.lower()
        if "登录" in desc:
            return "login.html"
        elif "列表" in desc or "表格" in desc:
            return "list.html"
        elif "表单" in desc:
            return "form.html"
        else:
            return "index.html"

    def _generate_code(self, feature: str, description: str) -> str:
        """根据需求生成对应的HTML代码"""

        if "登录" in feature:
            return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>登录页面</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.2);
            width: 100%;
            max-width: 400px;
        }
        .login-container h2 {
            text-align: center;
            margin-bottom: 30px;
            color: #333;
            font-size: 24px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            margin-bottom: 6px;
            color: #555;
            font-weight: 500;
        }
        .form-group input {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e1e5e9;
            border-radius: 8px;
            font-size: 15px;
            transition: border-color 0.3s;
        }
        .form-group input:focus {
            outline: none;
            border-color: #667eea;
        }
        .btn-login {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.3s;
        }
        .btn-login:hover { opacity: 0.9; }
        .error-msg {
            color: #e74c3c;
            font-size: 13px;
            margin-top: 4px;
            display: none;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h2>用户登录</h2>
        <form id="loginForm">
            <div class="form-group">
                <label for="username">用户名</label>
                <input type="text" id="username" placeholder="请输入用户名" required>
                <div class="error-msg" id="usernameError">请输入用户名</div>
            </div>
            <div class="form-group">
                <label for="password">密码</label>
                <input type="password" id="password" placeholder="请输入密码" required>
                <div class="error-msg" id="passwordError">请输入密码</div>
            </div>
            <button type="submit" class="btn-login">登 录</button>
        </form>
    </div>
    <script>
        document.getElementById('loginForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const username = document.getElementById('username').value.trim();
            const password = document.getElementById('password').value.trim();
            let valid = true;

            if (!username) {
                document.getElementById('usernameError').style.display = 'block';
                valid = false;
            } else {
                document.getElementById('usernameError').style.display = 'none';
            }

            if (!password) {
                document.getElementById('passwordError').style.display = 'block';
                valid = false;
            } else {
                document.getElementById('passwordError').style.display = 'none';
            }

            if (valid) {
                console.log('登录请求:', { username });
                alert('登录成功! (Demo)');
            }
        });
    </script>
</body>
</html>'''

        elif "列表" in feature or "表格" in feature:
            return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>数据列表</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f5f7fa;
            padding: 40px;
        }
        .container { max-width: 1000px; margin: 0 auto; }
        h1 { color: #333; margin-bottom: 24px; font-size: 28px; }
        .data-table {
            width: 100%;
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        }
        .data-table thead {
            background: #667eea;
            color: white;
        }
        .data-table th, .data-table td {
            padding: 14px 20px;
            text-align: left;
        }
        .data-table tbody tr {
            border-bottom: 1px solid #f0f0f0;
            transition: background 0.2s;
        }
        .data-table tbody tr:hover { background: #f8f9ff; }
        .status-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        .status-active { background: #e8f5e9; color: #2e7d32; }
        .status-pending { background: #fff3e0; color: #ef6c00; }
        .btn {
            padding: 6px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            margin-right: 4px;
        }
        .btn-edit { background: #e3f2fd; color: #1565c0; }
        .btn-delete { background: #fce4ec; color: #c62828; }
    </style>
</head>
<body>
    <div class="container">
        <h1>数据管理列表</h1>
        <table class="data-table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>名称</th>
                    <th>状态</th>
                    <th>创建时间</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody id="tableBody">
                <!-- 数据由JS动态渲染 -->
            </tbody>
        </table>
    </div>
    <script>
        const mockData = [
            { id: 1, name: '项目Alpha', status: 'active', created: '2026-05-20' },
            { id: 2, name: '项目Beta', status: 'pending', created: '2026-05-21' },
            { id: 3, name: '项目Gamma', status: 'active', created: '2026-05-22' },
        ];

        function renderTable() {
            const tbody = document.getElementById('tableBody');
            tbody.innerHTML = mockData.map(item => `
                <tr>
                    <td>${item.id}</td>
                    <td>${item.name}</td>
                    <td><span class="status-badge status-${item.status}">${item.status}</span></td>
                    <td>${item.created}</td>
                    <td>
                        <button class="btn btn-edit" onclick="editItem(${item.id})">编辑</button>
                        <button class="btn btn-delete" onclick="deleteItem(${item.id})">删除</button>
                    </td>
                </tr>
            `).join('');
        }

        function editItem(id) { console.log('编辑:', id); alert('编辑功能 (Demo)'); }
        function deleteItem(id) { console.log('删除:', id); alert('删除功能 (Demo)'); }

        renderTable();
    </script>
</body>
</html>'''

        else:
            return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{feature}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f5f7fa;
            padding: 40px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        .card {{
            background: white;
            padding: 48px;
            border-radius: 16px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.08);
            text-align: center;
            max-width: 500px;
        }}
        .card h1 {{ color: #333; margin-bottom: 16px; }}
        .card p {{ color: #666; line-height: 1.6; }}
        .card .btn {{
            margin-top: 24px;
            padding: 12px 32px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            cursor: pointer;
        }}
    </style>
</head>
<body>
    <div class="card">
        <h1>{feature}</h1>
        <p>此页面由<strong>前端开发AI</strong>自动生成<br>需求: {description}</p>
        <button class="btn" onclick="alert('交互正常!')">点击测试</button>
    </div>
</body>
</html>'''
