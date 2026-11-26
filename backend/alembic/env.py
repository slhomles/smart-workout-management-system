"""
Alembic env (async) — doc 05 §8.1.

- include_schemas=True: lược đồ nằm ở nhiều schema (auth, body, training...).
- target_metadata = Base.metadata, nạp mọi module trong app.models để autogenerate thấy đủ model.
- Autogenerate KHÔNG hiểu view, hàm, trigger, partial index đặc thù (doc 05 §8.1): các thứ đó viết tay
  bằng op.execute(...). `include_object` bên dưới bỏ qua bảng chỉ có trong DB mà chưa có model, để
  autogenerate không đề xuất xoá chúng.
"""

import asyncio
import importlib
import pkgutil
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import app.models
from app.core.config import get_settings
from app.core.database import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

for module in pkgutil.iter_modules(app.models.__path__):
    importlib.import_module(f"app.models.{module.name}")

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    if type_ == "table" and reflected and compare_to is None:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(get_settings().DATABASE_URL, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
