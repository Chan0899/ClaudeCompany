"""
工作区管理 - 本地文件系统读写, 跨进程文件锁, 项目汇总
"""
import os
import shutil
import time
import random
from config import WORKSPACE_DIR


class FileLock:
    """
    跨进程文件锁 (解决 threading.Lock 无法跨越 Claude 子进程的问题)

    使用 .lock 标记文件实现:
    - 获取锁: 创建 .lock 文件, 如果已存在则等待
    - 释放锁: 删除 .lock 文件
    - 超时: 默认 30 秒, 防止死锁
    """

    def __init__(self, filepath: str, timeout: float = 30.0):
        self._lockfile = filepath + ".lock"
        self._timeout = timeout

    def acquire(self) -> bool:
        """尝试获取锁, 返回是否成功"""
        deadline = time.time() + self._timeout
        while time.time() < deadline:
            try:
                # O_CREAT | O_EXCL: 原子创建, 文件已存在则抛异常
                fd = os.open(self._lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return True
            except OSError:
                # 锁被占用, 等待随机时间后重试
                time.sleep(0.1 + random.random() * 0.2)
        return False

    def release(self):
        """释放锁"""
        try:
            os.remove(self._lockfile)
        except OSError:
            pass  # 锁文件可能已被删除

    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(f"无法获取文件锁: {self._lockfile} (超时 {self._timeout}s)")
        return self

    def __exit__(self, *args):
        self.release()


class Workspace:
    """统一代码工作区: 创建目录、读写文件、跨进程锁、项目汇总"""

    def __init__(self):
        self.ensure_dirs()

    def ensure_dirs(self):
        """确保工作区子目录存在"""
        for sub in ["frontend", "backend", "tests", "_board", "_state", "projects"]:
            os.makedirs(os.path.join(WORKSPACE_DIR, sub), exist_ok=True)

    def write_file(self, role: str, filename: str, content: str) -> str:
        """写入文件 (原子写入 + 跨进程锁)"""
        role_dir = os.path.join(WORKSPACE_DIR, role)
        os.makedirs(role_dir, exist_ok=True)

        filepath = os.path.join(role_dir, filename)
        tmppath = filepath + ".tmp"

        with FileLock(filepath):
            with open(tmppath, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmppath, filepath)

        return filepath

    def read_file(self, role: str, filename: str) -> str:
        """读取文件内容"""
        filepath = os.path.join(WORKSPACE_DIR, role, filename)
        if not os.path.exists(filepath):
            return ""
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()

    def list_files(self) -> list[dict]:
        """列出工作区所有代码文件 (树形结构, 排除系统目录)"""
        tree = []
        if not os.path.exists(WORKSPACE_DIR):
            return tree

        for role in ["frontend", "backend", "tests"]:
            role_dir = os.path.join(WORKSPACE_DIR, role)
            if not os.path.exists(role_dir):
                continue
            files = []
            for fname in sorted(os.listdir(role_dir)):
                if fname.startswith("_") or fname.endswith(".tmp") or fname.endswith(".lock"):
                    continue
                fpath = os.path.join(role_dir, fname)
                if os.path.isfile(fpath):
                    files.append({
                        "name": fname,
                        "path": f"{role}/{fname}",
                        "size": os.path.getsize(fpath),
                        "role": role
                    })
            if files:
                tree.append({
                    "role": role,
                    "role_name": {"frontend": "前端", "backend": "后端", "tests": "测试"}.get(role, role),
                    "files": files
                })

        return tree

    def list_all_code_files(self) -> dict[str, list[str]]:
        """获取所有角色产出的文件列表 {role: [filepath, ...]}"""
        result = {}
        for role in ["frontend", "backend", "tests"]:
            role_dir = os.path.join(WORKSPACE_DIR, role)
            if os.path.exists(role_dir):
                result[role] = [
                    os.path.join(role_dir, f)
                    for f in os.listdir(role_dir)
                    if not f.startswith("_") and not f.endswith(".tmp") and not f.endswith(".lock")
                    and os.path.isfile(os.path.join(role_dir, f))
                ]
            else:
                result[role] = []
        return result

    def aggregate_project(self, project_name: str) -> str:
        """
        项目汇总: 将各角色产出的文件复制到统一项目目录
        返回汇总目录路径
        """
        project_dir = os.path.join(WORKSPACE_DIR, "projects", project_name)
        os.makedirs(project_dir, exist_ok=True)

        files_copied = []
        for role in ["frontend", "backend", "tests"]:
            role_dir = os.path.join(WORKSPACE_DIR, role)
            if not os.path.exists(role_dir):
                continue
            # 为每个角色创建子目录
            dest_role_dir = os.path.join(project_dir, role)
            os.makedirs(dest_role_dir, exist_ok=True)

            for fname in os.listdir(role_dir):
                if fname.startswith("_") or fname.endswith(".tmp") or fname.endswith(".lock"):
                    continue
                src = os.path.join(role_dir, fname)
                dst = os.path.join(dest_role_dir, fname)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
                    files_copied.append(f"{role}/{fname}")

        # 生成 README.md
        readme_path = os.path.join(project_dir, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(f"# {project_name}\n\n")
            f.write(f"> 由多Claude协同系统自动生成\n\n")
            f.write("## 项目结构\n\n")
            for fc in files_copied:
                f.write(f"- `{fc}`\n")
            f.write(f"\n共 {len(files_copied)} 个文件\n")

        return project_dir

    def clear(self):
        """清空工作区"""
        if os.path.exists(WORKSPACE_DIR):
            shutil.rmtree(WORKSPACE_DIR)
        self.ensure_dirs()


# 全局单例
workspace = Workspace()
