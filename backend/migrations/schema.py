"""数据库迁移管理 — 轻量级版本管理（无需 Alembic 依赖）"""

import logging
import os
from pathlib import Path

import aiosqlite

logger = logging.getLogger("testforge")

# 迁移版本目录
MIGRATIONS_DIR = Path(__file__).parent / "versions"


async def get_current_version(db_path: str) -> int:
    """获取当前数据库迁移版本"""
    async with aiosqlite.connect(db_path) as db:
        try:
            cursor = await db.execute("SELECT version FROM schema_migrations LIMIT 1")
            row = await cursor.fetchone()
            return row[0] if row else 0
        except aiosqlite.OperationalError:
            return 0


async def set_version(db_path: str, version: int):
    """更新迁移版本记录"""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)"
        )
        await db.execute("DELETE FROM schema_migrations")
        await db.execute("INSERT INTO schema_migrations (version) VALUES (?)", [version])
        await db.commit()


async def run_migrations(db_path: str) -> dict:
    """执行所有待运行的迁移

    迁移文件命名: 001_init.py, 002_add_index.py ...
    每个文件包含 async def upgrade(db) 函数

    Returns:
        {"applied": [int], "current": int, "status": "ok"|"error"}
    """
    current = await get_current_version(db_path)
    applied = []

    migrations = sorted(MIGRATIONS_DIR.glob("*.py"))
    migration_nums = []
    for m in migrations:
        if m.stem.startswith("_"):
            continue
        try:
            num = int(m.stem.split("_")[0])
            if num > current:
                migration_nums.append((num, m))
        except ValueError:
            continue

    if not migration_nums:
        return {"applied": [], "current": current, "status": "ok"}

    for num, mpath in migration_nums:
        try:
            async with aiosqlite.connect(db_path) as db:
                await _apply_migration(db, mpath)
                await db.commit()
            applied.append(num)
            logger.info("已应用迁移: %s", mpath.name)
        except Exception as e:
            logger.error("迁移失败 %s: %s", mpath.name, e)
            return {"applied": applied, "current": current, "status": "error", "error": str(e)}

    final = applied[-1] if applied else current
    await set_version(db_path, final)

    return {"applied": applied, "current": final, "status": "ok"}


async def _apply_migration(db: aiosqlite.Connection, migration_path: Path):
    """加载并执行单个迁移文件"""
    import importlib.util

    spec = importlib.util.spec_from_file_location(migration_path.stem, migration_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载迁移文件: {migration_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "upgrade"):
        raise RuntimeError(f"迁移文件缺少 upgrade 函数: {migration_path}")

    await module.upgrade(db)
