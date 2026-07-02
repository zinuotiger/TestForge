"""数据库持久化层 — SQLite / PostgreSQL 双后端

架构:
  - DatabaseBackend 抽象基类：定义 CRUD 接口
  - SQLiteBackend: 单连接 + WAL（本地/单用户）
  - PostgresBackend: 连接池 + 异步（团队/生产）
  - 自动根据 DATABASE_URL 选择后端

切换方式:
  DATABASE_URL=sqlite+aiosqlite:///testforge.db        → SQLite
  DATABASE_URL=postgresql+asyncpg://user:pass@host/db  → PostgreSQL
"""

import json
import re
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional

from backend.config import settings
from backend.models import TestCase, ExecutionResult

logger = logging.getLogger("testforge")


# ============ 数据库后端抽象 ============

class DatabaseBackend(ABC):
    """数据库后端抽象基类"""

    @abstractmethod
    async def init(self): ...

    @abstractmethod
    async def close(self): ...

    @abstractmethod
    async def execute(self, query: str, params: list = None): ...

    @abstractmethod
    async def fetchall(self, query: str, params: list = None) -> list: ...

    @abstractmethod
    async def fetchone(self, query: str, params: list = None): ...

    @abstractmethod
    async def commit(self): ...


# ============ SQLite 后端 ============

class SQLiteBackend(DatabaseBackend):
    """SQLite 后端 — 单连接 + WAL 模式"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = None
        self._lock = asyncio.Lock()

    async def init(self):
        import aiosqlite
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA busy_timeout=5000")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def execute(self, query: str, params: list = None):
        async with self._lock:
            cursor = await self._conn.execute(query, params or [])
            await self._conn.commit()
            return cursor

    async def commit(self):
        async with self._lock:
            await self._conn.commit()

    async def fetchall(self, query: str, params: list = None) -> list:
        async with self._lock:
            cursor = await self._conn.execute(query, params or [])
            return await cursor.fetchall()

    async def fetchone(self, query: str, params: list = None):
        async with self._lock:
            cursor = await self._conn.execute(query, params or [])
            return await cursor.fetchone()


# ============ PostgreSQL 后端 ============

class PostgresBackend(DatabaseBackend):
    """PostgreSQL 后端 — 连接池 + 异步

    需要安装: pip install asyncpg
    优势:
      - 多连接并发（解决 SQLite 单写锁瓶颈）
      - 分区表支持（大项目 100K+ 测试用例）
      - 事务隔离级别可配
    """

    def __init__(self, dsn: str):
        self.dsn = dsn
        self._pool = None
        self._min_size = 5
        self._max_size = 20

    async def init(self):
        try:
            import asyncpg
        except ImportError:
            raise RuntimeError(
                "PostgreSQL 后端需要 asyncpg: pip install asyncpg"
            )
        self._pool = await asyncpg.create_pool(
            dsn=self.dsn,
            min_size=self._min_size,
            max_size=self._max_size,
            command_timeout=30,
        )
        logger.info("PostgreSQL 连接池已创建: %s (min=%d, max=%d)",
                    self._sanitize_dsn(self.dsn), self._min_size, self._max_size)

    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def execute(self, query: str, params: list = None):
        async with self._pool.acquire() as conn:
            # asyncpg 用 $1, $2 占位符，需要转换 ? → $N
            pg_query = self._convert_placeholders(query)
            return await conn.execute(pg_query, *(params or []))

    async def commit(self):
        # asyncpg 默认自动提交，无需显式 commit
        pass

    async def fetchall(self, query: str, params: list = None) -> list:
        async with self._pool.acquire() as conn:
            pg_query = self._convert_placeholders(query)
            rows = await conn.fetch(pg_query, *(params or []))
            return [_PgRow(r) for r in rows]

    async def fetchone(self, query: str, params: list = None):
        async with self._pool.acquire() as conn:
            pg_query = self._convert_placeholders(query)
            row = await conn.fetchrow(pg_query, *(params or []))
            return _PgRow(row) if row else None

    @staticmethod
    def _convert_placeholders(query: str) -> str:
        """将 SQLite 风格 ? 占位符转为 PostgreSQL $N 风格"""
        result = []
        idx = 0
        for char in query:
            if char == "?":
                idx += 1
                result.append(f"${idx}")
            else:
                result.append(char)
        return "".join(result)

    @staticmethod
    def _sanitize_dsn(dsn: str) -> str:
        """DSN 脱敏（隐藏密码）"""
        return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", dsn)


class _PgRow:
    """asyncpg Record 适配器（模拟 aiosqlite.Row 的索引访问）"""

    def __init__(self, record):
        self._record = record
        self._keys = list(record.keys())

    def __getitem__(self, index):
        if isinstance(index, int):
            return self._record[self._keys[index]]
        return self._record[index]

    def __iter__(self):
        return iter(self._record.values())


# ============ 后端工厂 ============

_backend: Optional[DatabaseBackend] = None


def _create_backend() -> DatabaseBackend:
    """根据 DATABASE_URL 创建对应后端"""
    url = settings.database_url

    if url.startswith("postgresql") or url.startswith("postgres"):
        # postgresql+asyncpg://user:pass@host:port/db
        dsn = re.sub(r"^postgresql\+asyncpg://", "postgresql://", url)
        dsn = re.sub(r"^postgres\+asyncpg://", "postgresql://", dsn)
        return PostgresBackend(dsn)

    elif url.startswith("sqlite"):
        # sqlite+aiosqlite:///testforge.db → testforge.db
        m = re.match(r"sqlite(?:\+\w+)?:///(.*)", url)
        db_path = m.group(1) if m else "testforge.db"
        return SQLiteBackend(db_path)

    else:
        # 默认 SQLite
        return SQLiteBackend("testforge.db")


async def _get_backend() -> DatabaseBackend:
    """获取或创建后端单例"""
    global _backend
    if _backend is None:
        async with asyncio.Lock():
            if _backend is None:
                _backend = _create_backend()
                await _backend.init()
                logger.info("数据库后端已初始化: %s", type(_backend).__name__)
    return _backend


# ============ 公共 API（向后兼容）============

async def init_db():
    """初始化数据库"""
    db = await _get_backend()
    await db.execute("""
        CREATE TABLE IF NOT EXISTS test_cases (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT DEFAULT 'functional',
            tags TEXT DEFAULT '[]',
            status TEXT DEFAULT 'active',
            flaky_score REAL DEFAULT 0.0,
            health_score REAL DEFAULT 100.0,
            created_by TEXT DEFAULT 'manual',
            data TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS executions (
            execution_id TEXT PRIMARY KEY,
            test_id TEXT,
            status TEXT DEFAULT 'pending',
            duration_ms INTEGER DEFAULT 0,
            error_message TEXT,
            logs TEXT DEFAULT '[]',
            started_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    # 索引（PostgreSQL 支持更丰富的索引类型）
    try:
        await db.execute("CREATE INDEX IF NOT EXISTS idx_test_cases_status ON test_cases(status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_executions_test_id ON executions(test_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_executions_started ON executions(started_at DESC)")
    except Exception:
        pass


async def close_db():
    """关闭数据库连接"""
    global _backend
    if _backend is not None:
        await _backend.close()
        _backend = None


# ---- TestCase CRUD ----

async def list_tests(status: str = "all", tags: str = "") -> list[TestCase]:
    db = await _get_backend()
    query = (
        "SELECT id, name, type, tags, status, flaky_score, "
        "health_score, created_by, data FROM test_cases"
    )
    conditions = []
    params: list = []
    if status != "all":
        conditions.append("status = ?")
        params.append(status)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC"

    rows = await db.fetchall(query, params)
    results = [_row_to_testcase(r) for r in rows]

    if tags:
        wanted = {t.strip() for t in tags.split(",") if t.strip()}
        results = [tc for tc in results if wanted & set(tc.tags)]

    return results


async def get_test(test_id: str) -> TestCase | None:
    db = await _get_backend()
    row = await db.fetchone(
        "SELECT id, name, type, tags, status, flaky_score, "
        "health_score, created_by, data FROM test_cases WHERE id = ?",
        [test_id],
    )
    if not row:
        return None
    return _row_to_testcase(row)


async def save_test(tc: TestCase):
    db = await _get_backend()
    await db.execute(
        """INSERT OR REPLACE INTO test_cases
           (id, name, type, tags, status, flaky_score, health_score, created_by, data)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            tc.id, tc.name, tc.type.value, json.dumps(tc.tags),
            tc.status.value, tc.flaky_score, tc.health_score,
            tc.created_by, tc.model_dump_json(),
        ],
    )


async def delete_test(test_id: str):
    db = await _get_backend()
    await db.execute("DELETE FROM test_cases WHERE id = ?", [test_id])


async def quarantine_test(test_id: str):
    db = await _get_backend()
    await db.execute(
        "UPDATE test_cases SET status = 'quarantine' WHERE id = ?", [test_id]
    )


def _row_to_testcase(row) -> TestCase:
    return TestCase(
        id=row[0], name=row[1], type=row[2], tags=json.loads(row[3] or "[]"),
        status=row[4], flaky_score=row[5], health_score=row[6],
        created_by=row[7],
    )


# ---- Execution CRUD ----

async def save_execution(result: ExecutionResult):
    db = await _get_backend()
    await db.execute(
        """INSERT OR REPLACE INTO executions
           (execution_id, test_id, status, duration_ms, error_message, logs, started_at, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            result.execution_id, result.test_id, result.status.value,
            result.duration_ms, result.error_message,
            json.dumps(result.logs),
            result.started_at.isoformat() if result.started_at else None,
            result.completed_at.isoformat() if result.completed_at else None,
        ],
    )


async def get_execution(execution_id: str) -> dict | None:
    db = await _get_backend()
    row = await db.fetchone(
        "SELECT execution_id, test_id, status, duration_ms, "
        "error_message, logs, started_at, completed_at "
        "FROM executions WHERE execution_id = ?",
        [execution_id],
    )
    if not row:
        return None
    return {
        "execution_id": row[0], "test_id": row[1], "status": row[2],
        "duration_ms": row[3], "error_message": row[4],
        "logs": json.loads(row[5] or "[]"),
        "started_at": row[6], "completed_at": row[7],
    }


async def list_executions(limit: int = 50) -> list[dict]:
    db = await _get_backend()
    rows = await db.fetchall(
        "SELECT execution_id, test_id, status, duration_ms, "
        "error_message, logs, started_at, completed_at "
        "FROM executions ORDER BY started_at DESC LIMIT ?",
        [limit],
    )
    return [
        {
            "execution_id": r[0], "test_id": r[1], "status": r[2],
            "duration_ms": r[3], "error_message": r[4],
            "logs": json.loads(r[5] or "[]"),
            "started_at": r[6], "completed_at": r[7],
        }
        for r in rows
    ]


# ============ PostgreSQL 特有优化 ============

async def get_db_info() -> dict:
    """获取数据库信息（后端类型、连接状态）"""
    db = await _get_backend()
    info = {
        "backend": type(db).__name__,
        "database_url": settings.database_url.split("://")[0] + "://***",
    }
    if isinstance(db, PostgresBackend) and db._pool:
        info["pool_size"] = db._pool.get_size()
        info["idle_connections"] = db._pool.get_idle_size()
    return info
