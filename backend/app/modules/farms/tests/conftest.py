"""Shared PostgreSQL fixture: all test schemas and rows roll back on exit."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.base import Base


@pytest.fixture
def db():
    if os.getenv("AGROSHIFT_TEST_DB") != "1":
        pytest.skip("Set AGROSHIFT_TEST_DB=1 to run isolated PostGIS integration tests")
    from app.db.session import engine

    with engine.connect() as conn:
        transaction = conn.begin()
        schema = "farms_test_" + uuid4().hex
        try:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            conn.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
            scoped = conn.execution_options(schema_translate_map={None: schema})
            Base.metadata.create_all(scoped)
            with Session(bind=scoped, join_transaction_mode="create_savepoint") as session:
                yield session
        finally:
            transaction.rollback()
