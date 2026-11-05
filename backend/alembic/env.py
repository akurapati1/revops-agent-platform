import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app import models  # noqa: F401
from app.core.config import get_settings
from app.db import Base

target_metadata = Base.metadata
url = get_settings().database_url


def do_run(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True,
                      render_as_batch=connection.dialect.name == "sqlite")
    with context.begin_transaction():
        context.run_migrations()


async def run_online():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        await conn.run_sync(do_run)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_online())
