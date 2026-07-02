"""数据库执行器 — 执行 SQL 查询并验证断言

文档第二节 L3 执行层 6 种执行器之一。
支持 SQLite/PostgreSQL/MySQL，只读模式安全执行。
"""

import asyncio
import logging
import re
import time
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger("testforge")


# 只允许这些 SQL 语句（防注入/防破坏）
_ALLOWED_PREFIXES = ("SELECT", "WITH", "SHOW", "EXPLAIN", "PRAGMA")
_FORBIDDEN_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "REPLACE", "MERGE", "GRANT", "REVOKE",
)


class DBExecutor:
    """数据库查询执行器（只读安全模式）"""

    async def execute(
        self,
        connection: str,
        query: str,
        assertions: list[dict] = None,
        timeout: int = 10,
    ) -> dict:
        """执行 SQL 查询并验证断言

        Args:
            connection: 数据库连接字符串
                - sqlite:///path/to.db
                - postgresql://user:pass@host:5432/dbname
                - mysql://user:pass@host:3306/dbname
            query: SQL 查询语句（仅允许 SELECT/WITH/SHOW/EXPLAIN）
            assertions: 断言列表
            timeout: 超时秒数

        Returns:
            {
                "passed": bool,
                "rows": list[dict],
                "row_count": int,
                "duration_ms": int,
                "assertions": [{type, expected, actual, passed}],
                "error": str,
            }
        """
        result = {
            "passed": False,
            "rows": [],
            "row_count": 0,
            "duration_ms": 0,
            "assertions": [],
            "error": "",
        }

        # 安全校验
        safety = self._validate_query(query)
        if not safety["safe"]:
            result["error"] = safety["reason"]
            return result

        start = time.time()
        try:
            rows = await asyncio.wait_for(
                self._run_query(connection, query),
                timeout=timeout,
            )
            result["rows"] = rows
            result["row_count"] = len(rows)
        except asyncio.TimeoutError:
            result["error"] = f"查询超时 ({timeout}s)"
            result["duration_ms"] = int((time.time() - start) * 1000)
            return result
        except Exception as e:
            result["error"] = f"查询失败: {e}"
            result["duration_ms"] = int((time.time() - start) * 1000)
            return result

        result["duration_ms"] = int((time.time() - start) * 1000)

        # 验证断言
        all_passed = True
        for a in (assertions or []):
            a_result = self._check_assertion(a, result)
            result["assertions"].append(a_result)
            if not a_result["passed"]:
                all_passed = False

        result["passed"] = all_passed
        return result

    # ---- 安全校验 ----

    def _validate_query(self, query: str) -> dict:
        """校验 SQL 安全性（只读）"""
        stripped = query.strip().upper()
        if not stripped:
            return {"safe": False, "reason": "空查询"}

        # 检查是否以允许的前缀开头
        if not any(stripped.startswith(p) for p in _ALLOWED_PREFIXES):
            return {"safe": False, "reason": f"仅允许 {'/'.join(_ALLOWED_PREFIXES)} 语句"}

        # 检查危险关键词（注释/字符串中也可能误判，但宁误杀不漏）
        for kw in _FORBIDDEN_KEYWORDS:
            if re.search(rf"\b{kw}\b", stripped):
                return {"safe": False, "reason": f"禁止的 SQL 关键词: {kw}"}

        return {"safe": True, "reason": ""}

    # ---- 查询执行 ----

    async def _run_query(self, connection: str, query: str) -> list[dict]:
        """根据连接字符串路由到对应驱动"""
        if connection.startswith("sqlite"):
            return await self._run_sqlite(connection, query)
        elif connection.startswith("postgres"):
            return await self._run_postgres(connection, query)
        elif connection.startswith("mysql"):
            return await self._run_mysql(connection, query)
        else:
            raise ValueError(f"不支持的数据库类型: {connection}")

    async def _run_sqlite(self, connection: str, query: str) -> list[dict]:
        """SQLite 查询（同步驱动放线程池）"""
        import sqlite3
        from pathlib import Path

        # 解析路径: sqlite:///path.db 或 sqlite:///:memory:
        if ":///" in connection:
            db_path = connection.split(":///", 1)[1]
        elif "://" in connection:
            db_path = connection.split("://", 1)[1]
        else:
            db_path = "testforge.db"

        if db_path != ":memory:" and not Path(db_path).exists():
            raise FileNotFoundError(f"数据库文件不存在: {db_path}")

        def _sync():
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            try:
                cursor = conn.execute(query)
                rows = [dict(r) for r in cursor.fetchall()]
                return rows
            finally:
                conn.close()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync)

    async def _run_postgres(self, connection: str, query: str) -> list[dict]:
        """PostgreSQL 查询"""
        try:
            import asyncpg
        except ImportError:
            raise RuntimeError("asyncpg 未安装，无法连接 PostgreSQL")

        conn = await asyncpg.connect(connection)
        try:
            rows = await conn.fetch(query)
            return [dict(r) for r in rows]
        finally:
            await conn.close()

    async def _run_mysql(self, connection: str, query: str) -> list[dict]:
        """MySQL 查询"""
        try:
            import aiomysql
        except ImportError:
            raise RuntimeError("aiomysql 未安装，无法连接 MySQL")

        parsed = urlparse(connection)
        conn = await aiomysql.connect(
            host=parsed.hostname or "localhost",
            port=parsed.port or 3306,
            user=parsed.username or "root",
            password=parsed.password or "",
            db=parsed.path.lstrip("/"),
        )
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query)
                rows = await cur.fetchall()
                return list(rows)
        finally:
            conn.close()

    # ---- 断言校验 ----

    def _check_assertion(self, assertion: dict, result: dict) -> dict:
        """检查数据库断言"""
        a_type = assertion.get("type", "equals")
        expected = assertion.get("expected")
        actual = None
        passed = False

        if a_type == "row_count":
            actual = result["row_count"]
            if isinstance(expected, list):
                passed = actual in expected
            else:
                passed = actual == expected

        elif a_type == "equals":
            path = assertion.get("path", "")
            actual = self._extract_value(result["rows"], path)
            passed = actual == expected

        elif a_type == "contains":
            path = assertion.get("path", "")
            actual = self._extract_value(result["rows"], path)
            passed = expected in actual if actual is not None else False

        elif a_type == "not_empty":
            actual = result["row_count"]
            passed = actual > 0

        return {
            "type": a_type,
            "expected": expected,
            "actual": actual,
            "passed": passed,
        }

    def _extract_value(self, rows: list[dict], path: str) -> Any:
        """从查询结果提取值 ($.rows[0].field)"""
        if not path or not rows:
            return None
        # $.rows[0].stock → rows[0]["stock"]
        clean = path.lstrip("$").lstrip(".")
        if clean.startswith("rows"):
            clean = clean[len("rows"):].lstrip(".")

        # 解析 [0].field
        m = re.match(r"\[(\d+)\]\.?\.?(.*)", clean)
        if m:
            idx = int(m.group(1))
            field = m.group(2)
            if idx < len(rows):
                return rows[idx].get(field)
        return None


# 全局单例
db_executor = DBExecutor()
