"""初始迁移 — 创建基础表结构"""

PLATFORM_SCHEMA = """
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
);

CREATE TABLE IF NOT EXISTS executions (
    execution_id TEXT PRIMARY KEY,
    test_id TEXT,
    status TEXT DEFAULT 'pending',
    duration_ms INTEGER DEFAULT 0,
    error_message TEXT,
    logs TEXT DEFAULT '[]',
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_test_cases_status ON test_cases(status);
CREATE INDEX IF NOT EXISTS idx_executions_status ON executions(status);
CREATE INDEX IF NOT EXISTS idx_executions_started ON executions(started_at);
"""


async def upgrade(db):
    """创建初始表结构"""
    for statement in PLATFORM_SCHEMA.strip().split(";"):
        stmt = statement.strip()
        if stmt:
            await db.execute(stmt + ";")
