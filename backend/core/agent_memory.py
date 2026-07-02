"""Agent 经验记忆 — 长期累积成功/失败经验

针对图片中"记忆/经验累积（上次这里失败）"需求：

设计：
  - 每次 Agent 任务执行后，将关键经验持久化到 SQLite
  - 经验类型：success_pattern（成功的 selector/动作组合）、failure_pattern（失败的操作）、
              site_specific（特定网站的特殊行为）、task_strategy（任务执行策略）
  - 下次执行类似任务时，检索相关经验作为 LLM 的额外上下文
  - 模式：selector 修复后保存新选择器，下次遇到同域名/同结构直接使用

存储：复用现有 SQLite (testforge.db)
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from backend.config import settings

logger = logging.getLogger("testforge")


class ExperienceType(str, Enum):
    SUCCESS_PATTERN = "success_pattern"     # 成功的操作模式
    FAILURE_PATTERN = "failure_pattern"     # 失败的操作
    SELECTOR_FIX = "selector_fix"           # 选择器修复记录
    SITE_BEHAVIOR = "site_behavior"         # 网站特殊行为
    TASK_STRATEGY = "task_strategy"         # 任务执行策略


@dataclass
class Experience:
    """一条经验记录"""
    id: int
    exp_type: ExperienceType
    domain: str                              # 关联域名
    key: str                                 # 检索 key（如 selector 模式、任务类型）
    context: dict                            # 上下文
    outcome: str                             # success/failure
    timestamp: float
    use_count: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.exp_type.value,
            "domain": self.domain,
            "key": self.key,
            "context": self.context,
            "outcome": self.outcome,
            "timestamp": self.timestamp,
            "use_count": self.use_count,
        }


class AgentMemory:
    """Agent 经验记忆库 — 跨任务长期学习

    主要能力：
    1. 记录成功/失败的操作模式
    2. 记录 selector 修复历史（下次遇到直接复用）
    3. 记录特定网站的行为（如某网站 SPA 跳转用 pushState）
    4. 记录任务级别的执行策略
    5. 按域名+key 检索相关经验
    """

    def __init__(self, db_path: str = "testforge.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化经验表"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_experiences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exp_type TEXT NOT NULL,
                    domain TEXT NOT NULL DEFAULT '',
                    key TEXT NOT NULL,
                    context TEXT DEFAULT '{}',
                    outcome TEXT DEFAULT 'success',
                    timestamp REAL NOT NULL,
                    use_count INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_experiences_domain_key
                ON agent_experiences(domain, key)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_experiences_type
                ON agent_experiences(exp_type)
            """)
            conn.commit()
        finally:
            conn.close()

    def record(
        self,
        exp_type: ExperienceType,
        key: str,
        context: dict,
        outcome: str = "success",
        domain: str = "",
    ) -> int:
        """记录一条经验"""
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                """INSERT INTO agent_experiences
                   (exp_type, domain, key, context, outcome, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    exp_type.value,
                    domain,
                    key[:200],
                    json.dumps(context, ensure_ascii=False)[:2000],
                    outcome,
                    time.time(),
                ),
            )
            exp_id = cur.lastrowid
            conn.commit()
            return exp_id
        finally:
            conn.close()

    def search(
        self,
        exp_type: Optional[ExperienceType] = None,
        domain: str = "",
        key_contains: str = "",
        limit: int = 5,
    ) -> list[Experience]:
        """检索相关经验"""
        conn = sqlite3.connect(self.db_path)
        try:
            sql = "SELECT id, exp_type, domain, key, context, outcome, timestamp, use_count FROM agent_experiences WHERE 1=1"
            params = []
            if exp_type:
                sql += " AND exp_type = ?"
                params.append(exp_type.value)
            if domain:
                sql += " AND (domain = ? OR domain = '')"
                params.append(domain)
            if key_contains:
                sql += " AND key LIKE ?"
                params.append(f"%{key_contains}%")
            sql += " ORDER BY use_count DESC, timestamp DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            return [
                Experience(
                    id=r[0],
                    exp_type=ExperienceType(r[1]),
                    domain=r[2],
                    key=r[3],
                    context=json.loads(r[4] or "{}"),
                    outcome=r[5],
                    timestamp=r[6],
                    use_count=r[7],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def increment_use_count(self, exp_id: int):
        """增加经验使用次数"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE agent_experiences SET use_count = use_count + 1 WHERE id = ?",
                (exp_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def record_selector_fix(self, domain: str, old_selector: str, new_selector: str):
        """记录选择器修复"""
        return self.record(
            exp_type=ExperienceType.SELECTOR_FIX,
            key=old_selector,
            context={"new_selector": new_selector, "domain": domain},
            outcome="success",
            domain=domain,
        )

    def get_suggested_selector(self, domain: str, old_selector: str) -> Optional[str]:
        """从记忆中查找已知的选择器修复建议"""
        exps = self.search(
            exp_type=ExperienceType.SELECTOR_FIX,
            domain=domain,
            key_contains=old_selector[:50],
            limit=1,
        )
        if exps:
            self.increment_use_count(exps[0].id)
            return exps[0].context.get("new_selector")
        return None

    def record_task_outcome(
        self,
        task: str,
        domain: str,
        success: bool,
        final_url: str,
        step_count: int,
        duration_ms: int,
    ):
        """记录一次任务执行的整体结果"""
        return self.record(
            exp_type=ExperienceType.TASK_STRATEGY,
            key=task[:100],
            context={
                "task": task,
                "success": success,
                "final_url": final_url,
                "step_count": step_count,
                "duration_ms": duration_ms,
            },
            outcome="success" if success else "failure",
            domain=domain,
        )

    def format_for_llm(self, domain: str, current_action: str = "") -> str:
        """把相关经验格式化为 LLM prompt 上下文

        Args:
            domain: 当前网站域名
            current_action: 当前准备执行的动作

        Returns:
            适合插入 LLM 提示词的字符串
        """
        exps = self.search(domain=domain, limit=8)
        if not exps:
            return ""

        lines = ["【历史经验】（来自过去类似任务的执行记录）"]
        for e in exps:
            ago_min = int((time.time() - e.timestamp) / 60)
            if ago_min < 1:
                ago_str = "刚刚"
            elif ago_min < 60:
                ago_str = f"{ago_min}分钟前"
            else:
                ago_str = f"{ago_min // 60}小时前"

            if e.exp_type == ExperienceType.SELECTOR_FIX:
                lines.append(
                    f"- [{ago_str}] 选择器修复: '{e.key}' → '{e.context.get('new_selector', '?')}' "
                    f"（被复用 {e.use_count} 次）"
                )
            elif e.exp_type == ExperienceType.FAILURE_PATTERN:
                lines.append(
                    f"- [{ago_str}] ⚠️ 失败模式: {e.key} 失败原因: {e.context.get('error', '?')}"
                )
            elif e.exp_type == ExperienceType.SUCCESS_PATTERN:
                lines.append(
                    f"- [{ago_str}] ✅ 成功模式: {e.key}（{e.context.get('strategy', '')}）"
                )
            elif e.exp_type == ExperienceType.TASK_STRATEGY:
                if e.context.get("success"):
                    lines.append(
                        f"- [{ago_str}] 类似任务成功: {e.context.get('task', e.key)[:50]} "
                        f"（{e.context.get('step_count')} 步, {e.context.get('duration_ms', 0)}ms）"
                    )
                else:
                    lines.append(
                        f"- [{ago_str}] ⚠️ 类似任务失败: {e.context.get('task', e.key)[:50]}"
                    )
            elif e.exp_type == ExperienceType.SITE_BEHAVIOR:
                lines.append(
                    f"- [{ago_str}] 📌 {domain} 行为: {e.key} → {e.context.get('action', '')}"
                )

        return "\n".join(lines)

    def stats(self) -> dict:
        """记忆库统计"""
        conn = sqlite3.connect(self.db_path)
        try:
            total = conn.execute("SELECT COUNT(*) FROM agent_experiences").fetchone()[0]
            by_type = dict(
                conn.execute(
                    "SELECT exp_type, COUNT(*) FROM agent_experiences GROUP BY exp_type"
                ).fetchall()
            )
            by_domain = dict(
                conn.execute(
                    "SELECT domain, COUNT(*) FROM agent_experiences WHERE domain != '' GROUP BY domain"
                ).fetchall()
            )
            return {
                "total": total,
                "by_type": by_type,
                "by_domain": by_domain,
                "top_used": [
                    {"id": r[0], "key": r[1], "use_count": r[2]}
                    for r in conn.execute(
                        "SELECT id, key, use_count FROM agent_experiences ORDER BY use_count DESC LIMIT 5"
                    ).fetchall()
                ],
            }
        finally:
            conn.close()


# 全局单例
agent_memory = AgentMemory()
