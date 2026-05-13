"""Alembic environment for Genovate.

This is a minimal Alembic env that does *not* import the application models –
Genovate uses raw asyncpg, not SQLAlchemy ORM. Migrations are therefore
written in raw SQL via `op.execute(...)` in the version files.

The database URL is taken from `app.core.config.settings` (env vars) when
available, otherwise the value in alembic.ini is used.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make the application importable so settings can be reused.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

try:  # Optional: pull the URL from app settings (env vars) when available.
    from app.core.config import settings  # type: ignore

    db_url = (
        f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    )
    config.set_main_option("sqlalchemy.url", db_url)
except Exception:  # noqa: BLE001 - fall back to alembic.ini value
    pass

# Genovate has no ORM metadata; migrations are raw SQL.
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
