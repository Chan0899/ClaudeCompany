"""
后端开发AI - 生成Python/Flask后端代码
"""
from core.executor_ai import ExecutorAI
from core.workspace import workspace


class BackendDevAI(ExecutorAI):
    """后端工程师AI: 生成API接口和业务逻辑代码"""

    def do_work(self, task: dict) -> dict:
        description = task.get("description", "")
        feature = task.get("feature", description)

        filename = self._pick_filename(description)
        code = self._generate_code(feature, description)

        filepath = workspace.write_file("backend", filename, code)

        return {
            "files": [f"backend/{filename}"],
            "filepath": filepath,
            "role": "backend"
        }

    def _pick_filename(self, description: str) -> str:
        desc = description.lower()
        if "登录" in desc or "认证" in desc:
            return "auth_api.py"
        elif "注册" in desc:
            return "register_api.py"
        elif "列表" in desc or "数据" in desc:
            return "data_api.py"
        else:
            return "api.py"

    def _generate_code(self, feature: str, description: str) -> str:
        """生成对应的后端API代码"""

        if "登录" in feature:
            return '''"""
用户认证API - 登录/登出
生成者: 后端开发AI
"""
from flask import Blueprint, request, jsonify
import hashlib
import time

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# 模拟用户数据 (实际项目应使用数据库)
MOCK_USERS = {
    "admin": {"password": "e10adc3949ba59abbe56e057f20f883e", "role": "admin"},
    "user1": {"password": "e10adc3949ba59abbe56e057f20f883e", "role": "user"},
}

# 模拟Session存储
SESSIONS = {}


def hash_password(password: str) -> str:
    """MD5哈希 (Demo用, 生产环境请用bcrypt)"""
    return hashlib.md5(password.encode()).hexdigest()


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    用户登录接口
    POST /api/auth/login
    Body: {"username": "admin", "password": "123456"}
    """
    data = request.get_json()
    if not data:
        return jsonify({"code": 400, "message": "请提供登录信息"}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({"code": 400, "message": "用户名和密码不能为空"}), 400

    # 验证用户
    user = MOCK_USERS.get(username)
    if not user or user['password'] != hash_password(password):
        return jsonify({"code": 401, "message": "用户名或密码错误"}), 401

    # 生成Session Token
    token = hashlib.md5(f"{username}{time.time()}".encode()).hexdigest()
    SESSIONS[token] = {
        "username": username,
        "role": user['role'],
        "login_time": time.time()
    }

    return jsonify({
        "code": 200,
        "message": "登录成功",
        "data": {
            "token": token,
            "username": username,
            "role": user['role']
        }
    })


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """用户登出"""
    token = request.headers.get('Authorization', '')
    SESSIONS.pop(token, None)
    return jsonify({"code": 200, "message": "已登出"})


@auth_bp.route('/check', methods=['GET'])
def check_auth():
    """检查登录状态"""
    token = request.headers.get('Authorization', '')
    session = SESSIONS.get(token)
    if session:
        return jsonify({"code": 200, "data": session})
    return jsonify({"code": 401, "message": "未登录"}), 401


def require_auth(f):
    """登录验证装饰器"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '')
        if not token or token not in SESSIONS:
            return jsonify({"code": 401, "message": "请先登录"}), 401
        return f(*args, **kwargs)
    return decorated
'''

        elif "列表" in feature or "数据" in feature:
            return '''"""
数据管理API - CRUD接口
生成者: 后端开发AI
"""
from flask import Blueprint, request, jsonify

data_bp = Blueprint('data', __name__, url_prefix='/api/data')

# 模拟数据库
ITEMS = [
    {"id": 1, "name": "项目Alpha", "status": "active", "created_at": "2026-05-20"},
    {"id": 2, "name": "项目Beta", "status": "pending", "created_at": "2026-05-21"},
    {"id": 3, "name": "项目Gamma", "status": "active", "created_at": "2026-05-22"},
]
_next_id = 4


@data_bp.route('/list', methods=['GET'])
def get_list():
    """获取数据列表, 支持分页和筛选"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    status = request.args.get('status', '')

    # 筛选
    filtered = ITEMS
    if status:
        filtered = [item for item in ITEMS if item['status'] == status]

    # 分页
    start = (page - 1) * page_size
    end = start + page_size
    page_data = filtered[start:end]

    return jsonify({
        "code": 200,
        "data": {
            "items": page_data,
            "total": len(filtered),
            "page": page,
            "page_size": page_size
        }
    })


@data_bp.route('/<int:item_id>', methods=['GET'])
def get_item(item_id):
    """获取单条数据"""
    item = next((i for i in ITEMS if i['id'] == item_id), None)
    if not item:
        return jsonify({"code": 404, "message": "数据不存在"}), 404
    return jsonify({"code": 200, "data": item})


@data_bp.route('/create', methods=['POST'])
def create_item():
    """创建新数据"""
    global _next_id
    data = request.get_json()
    new_item = {
        "id": _next_id,
        "name": data.get('name', ''),
        "status": data.get('status', 'pending'),
        "created_at": data.get('created_at', '')
    }
    _next_id += 1
    ITEMS.append(new_item)
    return jsonify({"code": 200, "message": "创建成功", "data": new_item})


@data_bp.route('/<int:item_id>', methods=['PUT'])
def update_item(item_id):
    """更新数据"""
    item = next((i for i in ITEMS if i['id'] == item_id), None)
    if not item:
        return jsonify({"code": 404, "message": "数据不存在"}), 404
    data = request.get_json()
    item.update({k: v for k, v in data.items() if k in item})
    return jsonify({"code": 200, "message": "更新成功", "data": item})


@data_bp.route('/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    """删除数据"""
    global ITEMS
    item = next((i for i in ITEMS if i['id'] == item_id), None)
    if not item:
        return jsonify({"code": 404, "message": "数据不存在"}), 404
    ITEMS = [i for i in ITEMS if i['id'] != item_id]
    return jsonify({"code": 200, "message": "删除成功"})
'''

        else:
            return f'''"""
{feature} - 后端API接口
生成者: 后端开发AI
需求: {description}
"""
from flask import Blueprint, request, jsonify

bp = Blueprint('feature', __name__, url_prefix='/api/feature')


@bp.route('/process', methods=['POST'])
def process():
    """处理请求"""
    data = request.get_json()
    if not data:
        return jsonify({{"code": 400, "message": "请提供数据"}}), 400

    # 业务逻辑处理
    result = {{
        "input": data,
        "processed": True,
        "message": "处理完成"
    }}

    return jsonify({{
        "code": 200,
        "message": "处理成功",
        "data": result
    }})


@bp.route('/status', methods=['GET'])
def status():
    """获取状态"""
    return jsonify({{
        "code": 200,
        "data": {{
            "service": "{feature}",
            "status": "running",
            "version": "1.0.0"
        }}
    }})
'''
