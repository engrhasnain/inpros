"""Tiny additive migration: create new tables and add new nullable columns to existing ones.

Enough for the pilot (columns are only ever added). Replace with Alembic before production.
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.db import Base


def migrate(engine: Engine) -> list[str]:
    Base.metadata.create_all(engine)
    added = []
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                if not col.nullable:
                    raise RuntimeError(f"Cannot add required column {table.name}.{col.name} automatically")
                ddl = col.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl}'))
                added.append(f"{table.name}.{col.name}")
    return added
