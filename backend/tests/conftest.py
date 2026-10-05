import pytest

from app.db import SessionLocal


@pytest.fixture
def db():
    """Each test gets a real session against the live Postgres (needed
    for pgvector columns - there's no SQLite equivalent). Changes are
    rolled back at teardown, so tests must not call db.commit()
    themselves - only db.flush() - or the rollback can't undo them.
    """
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()
