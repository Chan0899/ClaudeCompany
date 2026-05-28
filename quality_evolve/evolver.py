"""
Evolver - 自主复盘与经验进化

模块8: 基于记忆和数据的自动复盘、经验提炼、进化建议

复用:
  - data_store.query_errors() / query_task_metrics() / query_tool_stats()
  - memory_manager.TeamMemory / LongTermMemory
"""
import os
import time
from core.event_bus import event_bus


class Evolver:
    """
    自进化引擎

    功能:
      1. 分析近期数据和错误趋势
      2. 提炼经验教训
      3. 自动写入团队记忆和角色长期记忆
      4. 生成项目复盘报告
    """

    def __init__(self):
        self._lessons: list[dict] = []

    # ============================================================
    # 趋势分析
    # ============================================================

    def analyze_trends(self) -> dict:
        """
        分析近期系统运行趋势

        返回:
          {
            error_trend: "up"(上升)/"down"(下降)/"stable"(稳定),
            avg_task_time: 秒数,
            top_errors: [...],
            efficiency_by_role: {...},
            tool_usage: {...}
          }
        """
        try:
            from core.data_store import data_store

            # 错误统计
            errors = data_store.query_errors(limit=50)
            error_count = len(errors)

            # 任务效率
            metrics = data_store.query_task_metrics(recent_days=7)
            avg_time = sum(m["avg_seconds"] for m in metrics) / max(len(metrics), 1)

            # 工具使用
            tool_stats = data_store.query_tool_stats(recent_days=7)

            # 错误趋势 (简化: 对比本周和上周)
            error_trend = "stable"
            if error_count > 10:
                error_trend = "up"
            elif error_count < 3:
                error_trend = "down"

            # 高频错误归类
            error_types: dict[str, int] = {}
            for e in errors:
                etype = e.get("error_type", "unknown")
                error_types[etype] = error_types.get(etype, 0) + 1
            top_errors = sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:5]

            return {
                "error_trend": error_trend,
                "error_count": error_count,
                "avg_task_time": round(avg_time, 1),
                "role_efficiency": {m["role"]: m["avg_seconds"] for m in metrics},
                "top_errors": [{"type": t, "count": c} for t, c in top_errors],
                "tool_usage": {s["tool_name"]: s["call_count"] for s in tool_stats},
            }
        except Exception as e:
            return {"error": str(e)}

    # ============================================================
    # 经验提炼
    # ============================================================

    def generate_lessons(self) -> list[dict]:
        """
        从近期数据中提炼经验教训

        返回: [{"type": "lesson"/"insight"/"warning", "content": "...", "target_role": ""}, ...]
        """
        lessons = []
        trends = self.analyze_trends()
        if "error" in trends:
            return lessons

        # 1. 高频错误 → 警告
        for err in trends.get("top_errors", [])[:3]:
            lessons.append({
                "type": "warning",
                "content": f"近期高频错误类型: {err['type']} (出现{err['count']}次)。建议排查根因并修复。",
                "target_role": "all",
            })

        # 2. 最慢角色 → 优化建议
        role_eff = trends.get("role_efficiency", {})
        if role_eff:
            slowest = max(role_eff, key=role_eff.get)
            slowest_time = role_eff[slowest]
            if slowest_time > 60:  # 超过60秒视为慢
                lessons.append({
                    "type": "insight",
                    "content": (
                        f"角色 {slowest} 平均耗时 {slowest_time}秒, 是团队中效率最低的。"
                        f"建议检查其工具配置和任务分配是否合理。"
                    ),
                    "target_role": slowest,
                })

        # 3. 工具使用不均衡
        tool_usage = trends.get("tool_usage", {})
        if tool_usage:
            unused = [name for name, count in tool_usage.items() if count == 0]
            if unused:
                lessons.append({
                    "type": "insight",
                    "content": f"以下工具近期零使用: {', '.join(unused)}。检查是否绑定异常或未被合理调用。",
                    "target_role": "all",
                })

        self._lessons = lessons
        return lessons

    # ============================================================
    # 自动写入记忆
    # ============================================================

    def auto_write_lessons(self) -> int:
        """
        将提炼的经验自动写入团队记忆和角色长期记忆

        返回: 写入条数
        """
        lessons = self.generate_lessons()
        written = 0

        try:
            from core.memory_manager import TeamMemory, get_memory_manager

            team_mem = TeamMemory()

            for lesson in lessons:
                ts = time.strftime("%Y-%m-%d %H:%M")
                content = f"[{ts}] {lesson['content']}"

                if lesson["target_role"] == "all":
                    # 写入团队共享记忆
                    section = "高频问题FAQ" if lesson["type"] == "warning" else "通用项目经验"
                    team_mem.append(section, content)
                    written += 1
                else:
                    # 写入具体角色长期记忆
                    mm = get_memory_manager(lesson["target_role"])
                    mm.learn_experience(content, "工作经验")
                    written += 1

                # 同步到 data_store
                try:
                    from core.data_store import data_store
                    data_store.index_memory(
                        role_id=lesson.get("target_role", "all"),
                        memory_type="evolved",
                        title=f"[自进化] {lesson['type']}",
                        content=content,
                        source_file="evolver.auto_write_lessons",
                        tags=f"evolver,{lesson['type']}"
                    )
                except Exception:
                    pass

        except Exception:
            pass

        if written > 0:
            event_bus.publish("log", {
                "ai_id": "evolver",
                "ai_name": "自进化引擎",
                "message": f"自动写入 {written} 条经验教训到记忆系统"
            })

        return written

    # ============================================================
    # 项目复盘
    # ============================================================

    def retrospective(self, project_name: str) -> str:
        """
        生成项目复盘报告

        返回: Markdown 格式复盘文本
        """
        trends = self.analyze_trends()

        lines = [
            f"# 项目复盘: {project_name}",
            f"",
            f"> 自动生成于 {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"## 执行概况",
            f"- 近期错误数: {trends.get('error_count', 'N/A')}",
            f"- 错误趋势: {trends.get('error_trend', 'N/A')}",
            f"- 平均任务耗时: {trends.get('avg_task_time', 'N/A')}秒",
            f"",
            f"## 各角色效率",
        ]

        for role, avg in trends.get("role_efficiency", {}).items():
            lines.append(f"- {role}: {avg}秒/任务")

        lines.append(f"")
        lines.append(f"## 高频错误")
        for err in trends.get("top_errors", []):
            lines.append(f"- {err['type']}: {err['count']}次")

        lines.append(f"")
        lines.append(f"## 工具使用")
        for name, count in trends.get("tool_usage", {}).items():
            lines.append(f"- {name}: {count}次")

        lines.append(f"")
        lines.append(f"## 经验教训")
        for lesson in self._lessons:
            lines.append(f"- [{lesson['type']}] {lesson['content']}")

        if not self._lessons:
            lines.append("- (暂无 - 数据积累不足)")

        report = "\n".join(lines)

        # 写入团队记忆
        try:
            from core.memory_manager import TeamMemory
            TeamMemory().append("通用项目经验", report)
        except Exception:
            pass

        event_bus.publish("log", {
            "ai_id": "evolver",
            "ai_name": "自进化引擎",
            "message": f"项目复盘完成: {project_name}"
        })

        return report


# 全局单例
evolver = Evolver()
