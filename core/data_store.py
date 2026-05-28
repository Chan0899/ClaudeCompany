"""
统一资源持久层 - SQLite 数据仓库

模块4+6: 结构化数据存储 + 记忆索引

7张表:
  1. tool_calls        - 工具调用日志
  2. task_records      - 任务耗时记录
  3. error_logs        - 报错记录
  4. team_memory       - 团队记忆
  5. project_artifacts - 项目成果
  6. event_log         - 全量事件流水
  7. memory_index      - 记忆索引 (模块6)

查询接口 (为模块6 质控进化层准备):
  - query_tool_stats()      - 工具使用统计
  - query_task_metrics()    - 任务效率指标
  - query_errors()          - 错误查询
  - search_memory()         - 团队记忆搜索
  - get_project_history()   - 项目成果历史
"""
import os
import json
import time
import sqlite3
import threading
from config import WORKSPACE_DIR


# 数据库文件路径 (与原有 JSON 持久化同目录)
DB_DIR = os.path.join(WORKSPACE_DIR, "_state")
DB_PATH = os.path.join(DB_DIR, "data.db")


class DataStore:
    """
    SQLite 数据仓库

    线程安全, 自动建表, 统一记录所有系统事件。
    原有 persistence.py 保持不变, 此模块为增量能力。
    """

    def __init__(self):
        os.makedirs(DB_DIR, exist_ok=True)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    # ============================================================
    # 数据库初始化
    # ============================================================

    def _init_db(self):
        """建库建表 (幂等)"""
        with self._lock:
            self._conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")      # 写性能优化
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._create_tables()

    def _create_tables(self):
        """创建所有表 (IF NOT EXISTS, 幂等)"""
        cur = self._conn.cursor()

        # 1. 工具调用日志
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tool_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT NOT NULL,
                tool_category TEXT NOT NULL,
                role_id TEXT DEFAULT '',
                params_json TEXT DEFAULT '{}',
                elapsed_ms REAL DEFAULT 0,
                success INTEGER DEFAULT 1,
                error_msg TEXT DEFAULT '',
                created_at REAL NOT NULL
            )
        """)

        # 2. 任务耗时记录
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                task_desc TEXT DEFAULT '',
                assigned_role TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                created_at REAL,
                completed_at REAL,
                elapsed_seconds REAL DEFAULT 0
            )
        """)

        # 3. 报错记录
        cur.execute("""
            CREATE TABLE IF NOT EXISTS error_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_id TEXT DEFAULT '',
                error_type TEXT DEFAULT 'unknown',
                error_message TEXT DEFAULT '',
                stack_trace TEXT DEFAULT '',
                created_at REAL NOT NULL
            )
        """)

        # 4. 团队记忆
        cur.execute("""
            CREATE TABLE IF NOT EXISTS team_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_type TEXT NOT NULL,
                role_id TEXT DEFAULT '',
                title TEXT NOT NULL,
                content TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                created_at REAL NOT NULL
            )
        """)

        # 5. 项目成果
        cur.execute("""
            CREATE TABLE IF NOT EXISTS project_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT DEFAULT '',
                project_name TEXT NOT NULL,
                file_count INTEGER DEFAULT 0,
                file_list_json TEXT DEFAULT '[]',
                total_size_bytes INTEGER DEFAULT 0,
                created_at REAL NOT NULL
            )
        """)

        # 6. 全量事件流水
        cur.execute("""
            CREATE TABLE IF NOT EXISTS event_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                event_data_json TEXT DEFAULT '{}',
                created_at REAL NOT NULL
            )
        """)

        # 7. 记忆索引 (模块6: 三层记忆统一检索)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS memory_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                title TEXT DEFAULT '',
                content_preview TEXT DEFAULT '',
                source_file TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                created_at REAL NOT NULL
            )
        """)

        self._conn.commit()

    # ============================================================
    # 写入接口
    # ============================================================

    def record_tool_call(
        self, tool_name: str, tool_category: str, role_id: str = "",
        params: dict | None = None, elapsed_ms: float = 0,
        success: bool = True, error_msg: str = ""
    ):
        """记录工具调用"""
        self._execute(
            """INSERT INTO tool_calls
               (tool_name, tool_category, role_id, params_json, elapsed_ms, success, error_msg, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (tool_name, tool_category, role_id,
             json.dumps(params or {}, ensure_ascii=False),
             elapsed_ms, 1 if success else 0, error_msg, time.time())
        )

    def record_task(
        self, task_id: str, task_desc: str = "", assigned_role: str = "",
        status: str = "pending"
    ):
        """记录或更新任务 (upsert: 按 task_id 去重)"""
        existing = self._query_one(
            "SELECT id, created_at FROM task_records WHERE task_id = ?", (task_id,)
        )
        if existing:
            if status in ("done", "approved", "rejected", "pending_approval"):
                completed_at = time.time()
                created_at = existing[1]
                elapsed = completed_at - created_at if created_at else 0
                self._execute(
                    """UPDATE task_records
                       SET status=?, completed_at=?, elapsed_seconds=?
                       WHERE task_id=?""",
                    (status, completed_at, round(elapsed, 1), task_id)
                )
        else:
            self._execute(
                """INSERT INTO task_records
                   (task_id, task_desc, assigned_role, status, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (task_id, task_desc, assigned_role, status, time.time())
            )

    def record_error(
        self, source: str, error_message: str, source_id: str = "",
        error_type: str = "unknown", stack_trace: str = ""
    ):
        """记录错误"""
        self._execute(
            """INSERT INTO error_logs
               (source, source_id, error_type, error_message, stack_trace, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source, source_id, error_type, error_message[:2000], stack_trace[:2000], time.time())
        )

    def save_memory(
        self, memory_type: str, title: str, content: str = "",
        role_id: str = "", tags: str = ""
    ):
        """
        保存团队记忆

        memory_type: decision(决策) | lesson(教训) | pattern(模式) | insight(洞察)
        """
        self._execute(
            """INSERT INTO team_memory
               (memory_type, role_id, title, content, tags, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (memory_type, role_id, title, content[:5000], tags, time.time())
        )

    def record_artifact(
        self, project_name: str, task_id: str = "",
        file_count: int = 0, file_list: list[str] | None = None,
        total_size_bytes: int = 0
    ):
        """记录项目成果"""
        self._execute(
            """INSERT INTO project_artifacts
               (task_id, project_name, file_count, file_list_json, total_size_bytes, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (task_id, project_name, file_count,
             json.dumps(file_list or [], ensure_ascii=False),
             total_size_bytes, time.time())
        )

    def record_event(self, event_type: str, event_data: dict | None = None):
        """记录全量事件流水"""
        self._execute(
            """INSERT INTO event_log
               (event_type, event_data_json, created_at)
               VALUES (?, ?, ?)""",
            (event_type, json.dumps(event_data or {}, ensure_ascii=False, default=str), time.time())
        )

    # ============================================================
    # 查询接口 (为模块6 质控进化层准备)
    # ============================================================

    def query_tool_stats(self, recent_days: int = 7) -> list[dict]:
        """工具使用统计: 各工具调用次数、成功率、平均耗时"""
        cutoff = time.time() - recent_days * 86400
        rows = self._query_all(
            """SELECT tool_name, tool_category,
                      COUNT(*) as call_count,
                      SUM(success) as success_count,
                      ROUND(AVG(elapsed_ms), 1) as avg_ms
               FROM tool_calls
               WHERE created_at > ?
               GROUP BY tool_name
               ORDER BY call_count DESC""",
            (cutoff,)
        )
        return [
            {"tool_name": r[0], "category": r[1], "call_count": r[2],
             "success_rate": round(r[3]/r[2]*100, 1) if r[2] else 0, "avg_ms": r[4]}
            for r in rows
        ]

    def query_task_metrics(self, recent_days: int = 7) -> list[dict]:
        """任务效率指标: 各角色任务数、平均耗时"""
        cutoff = time.time() - recent_days * 86400
        rows = self._query_all(
            """SELECT assigned_role,
                      COUNT(*) as task_count,
                      ROUND(AVG(elapsed_seconds), 1) as avg_seconds,
                      SUM(CASE WHEN status IN ('done','approved') THEN 1 ELSE 0 END) as completed
               FROM task_records
               WHERE created_at > ?
               GROUP BY assigned_role
               ORDER BY task_count DESC""",
            (cutoff,)
        )
        return [
            {"role": r[0] or "unknown", "task_count": r[1],
             "avg_seconds": r[2], "completed": r[3]}
            for r in rows
        ]

    def query_errors(self, limit: int = 20, source: str = "") -> list[dict]:
        """查询最近N条错误 (可按来源过滤)"""
        if source:
            rows = self._query_all(
                "SELECT source, error_type, error_message, created_at FROM error_logs "
                "WHERE source=? ORDER BY created_at DESC LIMIT ?",
                (source, limit)
            )
        else:
            rows = self._query_all(
                "SELECT source, error_type, error_message, created_at FROM error_logs "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
        return [
            {"source": r[0], "error_type": r[1], "error_message": r[2][:200],
             "created_at": r[3]}
            for r in rows
        ]

    def search_memory(self, keywords: str = "", memory_type: str = "", limit: int = 20) -> list[dict]:
        """搜索团队记忆 (支持关键词 + 类型过滤)"""
        sql = "SELECT memory_type, role_id, title, content, tags, created_at FROM team_memory WHERE 1=1"
        params: list = []
        if keywords:
            sql += " AND (title LIKE ? OR content LIKE ? OR tags LIKE ?)"
            kw = f"%{keywords}%"
            params.extend([kw, kw, kw])
        if memory_type:
            sql += " AND memory_type = ?"
            params.append(memory_type)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self._query_all(sql, tuple(params))
        return [
            {"memory_type": r[0], "role_id": r[1], "title": r[2],
             "content": r[3][:300], "tags": r[4], "created_at": r[5]}
            for r in rows
        ]

    def get_project_history(self, limit: int = 20) -> list[dict]:
        """获取项目成果历史"""
        rows = self._query_all(
            """SELECT project_name, task_id, file_count, total_size_bytes, created_at
               FROM project_artifacts
               ORDER BY created_at DESC LIMIT ?""",
            (limit,)
        )
        return [
            {"project_name": r[0], "task_id": r[1], "file_count": r[2],
             "total_size_bytes": r[3], "created_at": r[4]}
            for r in rows
        ]

    # ============================================================
    # 记忆索引接口 (模块6: 三层记忆统一检索)
    # ============================================================

    def index_memory(
        self, role_id: str, memory_type: str, title: str = "",
        content: str = "", source_file: str = "", tags: str = ""
    ):
        """将记忆条目写入索引表"""
        self._execute(
            """INSERT INTO memory_index
               (role_id, memory_type, title, content_preview, source_file, tags, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (role_id, memory_type, title, content[:500], source_file, tags, time.time())
        )

    def query_memories(
        self, keyword: str = "", role_id: str = "",
        memory_type: str = "", limit: int = 30
    ) -> list[dict]:
        """跨角色搜索记忆索引"""
        sql = "SELECT role_id, memory_type, title, content_preview, source_file, tags, created_at FROM memory_index WHERE 1=1"
        params: list = []
        if keyword:
            sql += " AND (title LIKE ? OR content_preview LIKE ? OR tags LIKE ?)"
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])
        if role_id:
            sql += " AND role_id = ?"
            params.append(role_id)
        if memory_type:
            sql += " AND memory_type = ?"
            params.append(memory_type)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self._query_all(sql, tuple(params))
        return [
            {"role_id": r[0], "memory_type": r[1], "title": r[2],
             "content_preview": r[3][:300], "source_file": r[4],
             "tags": r[5], "created_at": r[6]}
            for r in rows
        ]

    def get_memory_stats(self) -> dict:
        """记忆统计: 各角色各类型记忆数量"""
        rows = self._query_all(
            """SELECT role_id, memory_type, COUNT(*) as cnt,
                      MAX(created_at) as latest
               FROM memory_index
               GROUP BY role_id, memory_type
               ORDER BY role_id, memory_type"""
        )
        stats: dict[str, dict] = {}
        for r in rows:
            role = r[0] or "unknown"
            if role not in stats:
                stats[role] = {}
            stats[role][r[1]] = {"count": r[2], "latest_ts": r[3]}
        return stats

    # ============================================================
    # 统计概览 (给UI展示用)
    # ============================================================

    def get_overview(self) -> dict:
        """获取持久层概览统计"""
        return {
            "total_tool_calls": self._count("tool_calls"),
            "total_tasks": self._count("task_records"),
            "total_errors": self._count("error_logs"),
            "total_memories": self._count("team_memory"),
            "memory_indexed": self._count("memory_index"),
            "total_projects": self._count("project_artifacts"),
            "total_events": self._count("event_log"),
            "db_path": DB_PATH,
            "db_size_mb": round(os.path.getsize(DB_PATH) / (1024*1024), 2) if os.path.exists(DB_PATH) else 0,
        }

    # ============================================================
    # 内部工具方法
    # ============================================================

    def _execute(self, sql: str, params: tuple = ()):
        """执行写操作 (线程安全)"""
        with self._lock:
            try:
                self._conn.execute(sql, params)
                self._conn.commit()
            except sqlite3.Error as e:
                print(f"[DataStore] SQL写入错误: {e} | SQL: {sql[:80]}")

    def _query_one(self, sql: str, params: tuple = ()):
        """查询单行"""
        with self._lock:
            try:
                cur = self._conn.execute(sql, params)
                return cur.fetchone()
            except sqlite3.Error:
                return None

    def _query_all(self, sql: str, params: tuple = ()) -> list:
        """查询多行"""
        with self._lock:
            try:
                cur = self._conn.execute(sql, params)
                return cur.fetchall()
            except sqlite3.Error:
                return []

    def _count(self, table: str) -> int:
        """计数"""
        row = self._query_one(f"SELECT COUNT(*) FROM {table}")
        return row[0] if row else 0

    @property
    def tables(self) -> list[str]:
        """列出所有表名"""
        rows = self._query_all("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        return [r[0] for r in rows]

    def close(self):
        """关闭数据库连接"""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None


# ============================================================
# 全局单例
# ============================================================
data_store = DataStore()
