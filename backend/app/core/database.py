from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

import psycopg
from fastapi import Depends
from psycopg.rows import DictRow, dict_row

from app.core.config import Settings, get_settings
from app.core.errors import ApiError


def get_database(config: Annotated[Settings, Depends(get_settings)]) -> Iterator[psycopg.Connection[DictRow]]:
    with database_connection(config) as connection:
        yield connection


@contextmanager
def database_connection(config: Settings) -> Iterator[psycopg.Connection[DictRow]]:
    if config.database_url is None:
        raise ApiError(503, "database_unavailable", "Database is not configured")

    with psycopg.connect(
        config.database_url.get_secret_value(),
        connect_timeout=5,
        prepare_threshold=None,
        row_factory=dict_row,
    ) as connection:
        connection.execute("SET LOCAL statement_timeout = '5s'")
        connection.execute("SET LOCAL TIME ZONE 'UTC'")
        extension = connection.execute("""
            SELECT pg_catalog.set_config('search_path', pg_catalog.format('pg_catalog, %I', n.nspname), true)
            FROM pg_catalog.pg_extension AS e
            JOIN pg_catalog.pg_namespace AS n ON n.oid = e.extnamespace
            WHERE e.extname = 'postgis'
        """).fetchone()
        if extension is None:
            raise ApiError(503, "database_unavailable", "Database schema is not installed")
        yield connection
