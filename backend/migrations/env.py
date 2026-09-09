"""Alembic environment.

Reads the connection string from `DATABASE_URL` rather than alembic.ini, and
runs it through the same `normalise_url` the app uses so that Render's
`postgres://` form works here too — otherwise migrations fail on deploy with a
dialect error while the app itself connects fine, which is a confusing pair of
symptoms to debug.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.db.models import Base
from app.db.session import database_url, normalise_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_url = database_url()
if not _url:
    raise RuntimeError(
        "DATABASE_URL is not set. Alembic needs it to know which database to "
        "migrate; the application itself runs without one."
    )
config.set_main_option("sqlalchemy.url", normalise_url(_url))


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Without compare_type an int -> numeric change is silently
            # ignored by autogenerate, which for money columns is exactly the
            # migration you most want to catch.
            compare_type=True,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
