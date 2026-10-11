"""测试夹具：SQLite 会话 + 资源加载。

注意：必须在导入 `app.*` 之前设置环境变量，否则 config 会读取默认 MySQL 地址。
"""

from __future__ import annotations

import os
from collections.abc import Iterator

os.environ["DATABASE_URL"] = "sqlite:///./_test.db"
os.environ["STORAGE_ROOT"] = "./data/images"
os.environ["PLAN_STORE_ROOT"] = "./data/plans"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["RUNNER_TOKEN"] = "test-runner-token"
os.environ["ENVIRONMENT"] = "development"

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.core.database import Base  # noqa: E402
from app.models import ALL_MODELS  # noqa: F401,E402
from app.services.uuid_provider import new_uuid  # noqa: E402

TEST_WORKSPACE_ID = "11111111-1111-4111-8111-111111111111"
TEST_USER_ID = "22222222-2222-4222-8222-222222222222"


@pytest.fixture(scope="session")
def engine():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine) -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    maker = sessionmaker(bind=connection, autoflush=False, expire_on_commit=False, future=True)
    db = maker()
    try:
        yield db
    finally:
        db.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def workspace_id() -> str:
    return TEST_WORKSPACE_ID


@pytest.fixture()
def user_id() -> str:
    return TEST_USER_ID


@pytest.fixture()
def operation_key() -> str:
    return new_uuid()
