"""Shared test setup: a real Postgres test database.

How it works:
  * Once per test run, a separate database (the dev one with "_test" added to
    its name) is created, wiped, and built from scratch by running ALL of our
    Alembic migrations. So these tests also prove the migrations work.
  * Before each database test, every table is emptied.
  * The app is pointed at the test database for the duration of each test.
Your development data is never touched.
"""

import os
from dataclasses import dataclass
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.user import User

ROOT = Path(__file__).resolve().parent.parent
PASSWORD = "TestPassword123"


def _test_database_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    url = make_url(settings.database_url)
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


def _build_test_database(url_string: str) -> None:
    url = make_url(url_string)

    # 1. Create the test database if it doesn't exist yet.
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": url.database},
            )
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin.dispose()

    # 2. Wipe it completely, so every run starts from nothing.
    engine = create_engine(url_string)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
    finally:
        engine.dispose()

    # 3. Build the tables by running every migration.
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", url_string.replace("%", "%%"))
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
def engine():
    url = _test_database_url()
    _build_test_database(url)
    test_engine = create_engine(url, pool_pre_ping=True)
    yield test_engine
    test_engine.dispose()


@pytest.fixture()
def client(engine):
    """A test client whose requests use the test database, starting empty."""
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

    test_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@dataclass
class Account:
    id: int
    email: str
    headers: dict


@pytest.fixture()
def make_account(client, engine):
    """Register a user, optionally give them a role, log in, return their headers."""

    def _make(email: str, *, role=None, timezone: str = "UTC") -> Account:
        response = client.post(
            "/users",
            json={
                "email": email,
                "password": PASSWORD,
                "full_name": "Test User",
                "timezone": timezone,
            },
        )
        assert response.status_code == 201, response.text
        user_id = response.json()["id"]

        if role is not None:
            with Session(engine) as session:
                session.get(User, user_id).role = role
                session.commit()

        login = client.post("/auth/login", data={"username": email, "password": PASSWORD})
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        return Account(user_id, email, {"Authorization": f"Bearer {token}"})

    return _make
