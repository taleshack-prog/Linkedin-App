"""Configuração de ambiente do Alembic.

- A URL do banco vem da env DATABASE_URL (mesma usada pela aplicação), então
  os comandos funcionam igualmente no docker local e no pre-deploy do Railway.
- target_metadata vem dos models — `alembic revision --autogenerate` compara
  o banco com app/models.py.
- include_object preserva índices criados fora dos models (ex.: parciais do
  schema original), impedindo que o autogenerate os proponha para remoção.
"""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    raise RuntimeError("DATABASE_URL não definida — o Alembic usa a mesma URL da aplicação")
config.set_main_option("sqlalchemy.url", db_url)

# Importa os models para registrar todas as tabelas no metadata.
from app.database import Base  # noqa: E402
from app import models  # noqa: E402,F401

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    # Índice existe no banco mas não nos models -> manter (não propor drop).
    if type_ == "index" and reflected and compare_to is None:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=False,  # TEXT vs String são sinônimos no PG — sem falso diff
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
            include_object=include_object,
            compare_type=False,  # TEXT vs String são sinônimos no PG — sem falso diff
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
