"""
分层记忆系统 - 三层记忆管理器

模块5: 分层记忆系统开发

三层记忆:
  1. ShortTermMemory - 个人短期 (short_term.json), 任务内上下文
  2. LongTermMemory  - 个人长期 (long_term.md), 经验/踩坑/模板
  3. TeamMemory      - 团队共享 (team_shared.md), 规范/公共经验

数据流:
  任务开始 → load_context() 注入记忆到 prompt
  任务执行 → remember() 记录关键信息
  任务完成 → complete_task() 归档短期→长期
"""
import os
import json
import time
import threading
from typing import Optional


# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROLES_DIR = os.path.join(BASE_DIR, "roles")
MEMORY_CENTER_DIR = os.path.join(BASE_DIR, "memory_center")


# ============================================================
# ShortTermMemory - 个人短期记忆
# ============================================================

class ShortTermMemory:
    """
    短期记忆 (JSON)

    格式: [{"ts": 时间戳, "content": "内容", "source": "来源", "type": "info/error/decision"}, ...]

    生命周期: 单次任务内累积, 任务完成时归档清空
    """

    def __init__(self, role_id: str, max_entries: int = 50):
        self._role_id = role_id
        self._file = os.path.join(ROLES_DIR, role_id, "memory", "short_term.json")
        self._max = max_entries
        self._lock = threading.Lock()

    def load(self, limit: int = 20) -> list[dict]:
        """加载最近 N 条记忆"""
        entries = self._read_file()
        return entries[-limit:] if len(entries) > limit else entries

    def append(self, content: str, source: str = "", mtype: str = "info"):
        """追加一条记忆"""
        entry = {
            "ts": time.time(),
            "content": content,
            "source": source,
            "type": mtype
        }
        with self._lock:
            entries = self._read_file()
            entries.append(entry)
            # 裁剪超出的旧记录
            if len(entries) > self._max:
                entries = entries[-self._max:]
            self._write_file(entries)

    def archive(self) -> str | None:
        """
        归档: 将短期记忆摘要写入长期记忆, 然后清空

        返回归档摘要文本, 供调用方写入 long_term.md
        """
        entries = self._read_file()
        if not entries:
            return None

        # 生成摘要
        lines = [f"\n## 任务归档 - {time.strftime('%Y-%m-%d %H:%M')}\n"]
        lines.append(f"> 共 {len(entries)} 条记忆\n")
        for e in entries:
            ts = time.strftime("%H:%M", time.localtime(e["ts"]))
            tag = {"info": "", "error": "⚠", "decision": "📋"}.get(e["type"], "")
            lines.append(f"- {tag} [{ts}] {e['source']}: {e['content'][:200]}")

        summary = "\n".join(lines)

        # 清空短期记忆
        with self._lock:
            self._write_file([])

        return summary

    def clear(self):
        """强制清空短期记忆"""
        with self._lock:
            self._write_file([])

    @property
    def count(self) -> int:
        return len(self._read_file())

    def _read_file(self) -> list[dict]:
        try:
            if os.path.exists(self._file):
                with open(self._file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError):
            pass
        return []

    def _write_file(self, entries: list[dict]):
        os.makedirs(os.path.dirname(self._file), exist_ok=True)
        with open(self._file, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)


# ============================================================
# LongTermMemory - 个人长期记忆
# ============================================================

class LongTermMemory:
    """
    长期记忆 (Markdown)

    文件包含章节: ## 代码模板, ## 踩坑记录, ## 成功案例, ## 工作经验

    支持: 按章节追加、全文读取、关键词搜索
    """

    def __init__(self, role_id: str):
        self._role_id = role_id
        self._file = os.path.join(ROLES_DIR, role_id, "memory", "long_term.md")
        self._lock = threading.Lock()

    def load(self) -> str:
        """读取全文"""
        return self._read_file()

    def load_recent(self, max_chars: int = 2000) -> str:
        """读取最近内容 (限制字符数)"""
        content = self._read_file()
        if len(content) > max_chars:
            return content[-max_chars:] + "\n\n... (以上为最近长期记忆)"
        return content

    def append(self, section: str, content: str):
        """
        按章节追加内容

        section: "代码模板" | "踩坑记录" | "成功案例" | "工作经验"
        """
        existing = self._read_file()

        section_header = f"## {section}"
        new_entry = f"\n### {time.strftime('%Y-%m-%d %H:%M')}\n\n{content}\n"

        with self._lock:
            # 如果已有该章节, 在章节末尾追加
            # 否则在文件末尾新建章节
            if section_header in existing:
                # 找到该章节的结束位置 (下一个 ## 之前)
                idx = existing.find(section_header)
                next_section = existing.find("\n## ", idx + len(section_header))
                if next_section == -1:
                    # 最后一个章节, 追加到文件末尾
                    updated = existing.rstrip() + "\n" + new_entry
                else:
                    # 插入到下一个章节之前
                    updated = existing[:next_section] + new_entry + "\n" + existing[next_section:]
            else:
                updated = existing.rstrip() + f"\n\n{section_header}\n{new_entry}"

            self._write_file(updated)

    def search(self, keyword: str) -> list[str]:
        """全文搜索, 返回匹配的段落"""
        content = self._read_file()
        keyword_lower = keyword.lower()
        matches = []
        for line in content.split("\n"):
            if keyword_lower in line.lower() and line.strip():
                matches.append(line.strip()[:200])
        return matches[:20]

    def _read_file(self) -> str:
        try:
            if os.path.exists(self._file):
                with open(self._file, "r", encoding="utf-8") as f:
                    return f.read()
        except IOError:
            pass
        return ""

    def _write_file(self, content: str):
        os.makedirs(os.path.dirname(self._file), exist_ok=True)
        with open(self._file, "w", encoding="utf-8") as f:
            f.write(content)


# ============================================================
# TeamMemory - 团队共享记忆
# ============================================================

class TeamMemory:
    """
    团队共享记忆 (Markdown)

    文件: memory_center/team_shared.md
    全员可读, 由管理AI和质控层维护

    章节: 团队规范, 通用项目经验, 高频问题FAQ
    """

    def __init__(self):
        self._file = os.path.join(MEMORY_CENTER_DIR, "team_shared.md")
        self._lock = threading.Lock()

    def load(self) -> str:
        """读取全文"""
        return self._read_file()

    def load_summary(self, max_chars: int = 2000) -> str:
        """读取摘要"""
        content = self._read_file()
        if len(content) > max_chars:
            # 优先拿"团队规范"和"高频问题FAQ"
            sections = []
            for keyword in ["## 团队规范", "## 高频问题"]:
                idx = content.find(keyword)
                if idx >= 0:
                    end = content.find("\n## ", idx + 3)
                    if end == -1:
                        end = len(content)
                    sections.append(content[idx:end][:max_chars // 2])
            if sections:
                return "\n\n".join(sections)
            return content[:max_chars]
        return content

    def append(self, section: str, content: str):
        """按章节追加"""
        existing = self._read_file()
        section_header = f"## {section}"
        new_entry = f"\n### {time.strftime('%Y-%m-%d %H:%M')}\n\n{content}\n"

        with self._lock:
            if section_header in existing:
                idx = existing.find(section_header)
                next_section = existing.find("\n## ", idx + len(section_header))
                if next_section == -1:
                    updated = existing.rstrip() + "\n" + new_entry
                else:
                    updated = existing[:next_section] + new_entry + "\n" + existing[next_section:]
            else:
                updated = existing.rstrip() + f"\n\n{section_header}\n{new_entry}"

            self._write_file(updated)

        # 模块6: 同步写入 SQLite memory_index
        self._index_to_db(section, new_entry)

    def search(self, keyword: str) -> list[str]:
        """全文搜索"""
        content = self._read_file()
        keyword_lower = keyword.lower()
        matches = []
        for line in content.split("\n"):
            if keyword_lower in line.lower() and line.strip():
                matches.append(line.strip()[:200])
        return matches[:20]

    def _read_file(self) -> str:
        try:
            if os.path.exists(self._file):
                with open(self._file, "r", encoding="utf-8") as f:
                    return f.read()
        except IOError:
            pass
        return ""

    def _write_file(self, content: str):
        os.makedirs(os.path.dirname(self._file), exist_ok=True)
        with open(self._file, "w", encoding="utf-8") as f:
            f.write(content)


# ============================================================
# MemoryManager - 统一记忆门面
# ============================================================

class MemoryManager:
    """
    记忆管理器 - 封装三层记忆的统一入口

    用法:
      mm = MemoryManager("frontend_dev")

      # 任务开始
      context = mm.load_context()  # → 注入 prompt

      # 任务执行中
      mm.remember("API路径约定: /api/login", "公告板")
      mm.remember("表单验证逻辑有bug, JS未处理空值", "调试工具", mtype="error")

      # 任务完成
      mm.complete_task(task_summary="完成了登录页面开发")
    """

    def __init__(self, role_id: str):
        self._role_id = role_id
        self.short = ShortTermMemory(role_id)
        self.long = LongTermMemory(role_id)
        self.team = TeamMemory()

    # ============================================================
    # 任务生命周期
    # ============================================================

    def load_context(self, max_short: int = 20, max_long: int = 2000, max_team: int = 2000) -> str:
        """
        加载任务上下文: 短期 + 长期 + 团队记忆

        返回拼接后的文本, 注入到 AI prompt
        """
        parts = []

        # 团队记忆 (优先, 了解规范)
        team_content = self.team.load_summary(max_team)
        if team_content.strip():
            parts.append(f"【团队共享记忆 - 全员规范与经验】\n{team_content}")

        # 个人长期记忆
        long_content = self.long.load_recent(max_long)
        if long_content.strip():
            parts.append(f"【你的长期记忆 - 历史经验】\n{long_content}")

        # 短期记忆 (当前任务上下文)
        short_entries = self.short.load(max_short)
        if short_entries:
            lines = ["【当前任务上下文 - 短期记忆】"]
            for e in short_entries:
                ts = time.strftime("%H:%M", time.localtime(e["ts"]))
                lines.append(f"- [{ts}] {e['source']}: {e['content'][:150]}")
            parts.append("\n".join(lines))

        return "\n\n".join(parts) if parts else ""

    def remember(self, content: str, source: str = "", mtype: str = "info"):
        """记录一条短期记忆"""
        self.short.append(content, source, mtype)

    def complete_task(self, task_summary: str = "", save_section: str = "工作经验") -> str:
        """
        任务完成: 归档短期→长期

        返回归档文本
        """
        archive_text = self.short.archive()
        if archive_text:
            self.long.append(save_section, archive_text)

        if task_summary:
            self.long.append(save_section, f"📋 任务总结: {task_summary}")

        # 模块6: 同步写入 SQLite (团队记忆 + 记忆索引)
        try:
            from core.data_store import data_store
            data_store.save_memory(
                memory_type="task_archive",
                role_id=self._role_id,
                title=f"任务归档 - {time.strftime('%Y-%m-%d %H:%M')}",
                content=task_summary or (archive_text or ""),
                tags=f"{self._role_id},task_archive"
            )
            data_store.index_memory(
                role_id=self._role_id,
                memory_type="short_term",
                title=f"任务归档 - {time.strftime('%Y-%m-%d %H:%M')}",
                content=task_summary or (archive_text or ""),
                source_file=f"roles/{self._role_id}/memory/short_term.json",
                tags=f"{self._role_id},task_archive"
            )
        except Exception:
            pass

        return archive_text or ""

    def learn_experience(self, content: str, section: str = "工作经验"):
        """直接向长期记忆写入经验"""
        self.long.append(section, content)

    def search_memory(self, keyword: str) -> dict:
        """搜索所有记忆层"""
        return {
            "long_term": self.long.search(keyword),
            "team": self.team.search(keyword),
        }


# ============================================================
# 全局单例 (按角色缓存)
# ============================================================
_memory_managers: dict[str, MemoryManager] = {}
_mm_lock = threading.Lock()


def get_memory_manager(role_id: str) -> MemoryManager:
    """获取指定角色的 MemoryManager (缓存复用)"""
    with _mm_lock:
        if role_id not in _memory_managers:
            _memory_managers[role_id] = MemoryManager(role_id)
        return _memory_managers[role_id]
