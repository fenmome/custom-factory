"""FastAPI 接口冒烟测试（TestClient，SQLite + 本地存储）。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.core.security import hash_password
from app.main import app
from app.models import ALL_MODELS  # noqa: F401
from app.models.workspace import User, Workspace, WorkspaceMembership
from app.services import sku_service
from app.services.uuid_provider import new_uuid

WORKSPACE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
USER_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
EMAIL = "owner@example.com"
PASSWORD = "secret123"

# 该模块独占一份 SQLite 库：先清库再建表，保证幂等键不被历史运行污染
for _table in reversed(Base.metadata.sorted_tables):
    _table.drop(bind=engine, checkfirst=True)
Base.metadata.create_all(bind=engine)


@pytest.fixture(scope="module", autouse=True)
def seed():
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    if db.get(Workspace, WORKSPACE_ID) is None:
        db.add(Workspace(id=WORKSPACE_ID, display_name="默认工作空间", state="ACTIVE"))
        db.add(
            User(
                id=USER_ID,
                email=EMAIL,
                password_hash=hash_password(PASSWORD),
                display_name="Owner",
                state="ACTIVE",
                is_superuser=True,
            )
        )
        db.add(
            WorkspaceMembership(
                id=new_uuid(),
                workspace_id=WORKSPACE_ID,
                user_id=USER_ID,
                role="OWNER",
                status="ACTIVE",
            )
        )
        sku_service.create_config(
            session=db,
            workspace_id=WORKSPACE_ID,
            product_type_code="UV_DTF",
            display_name="定制水晶标",
            prefix="DZUVDTF",
        )
        db.commit()
    db.close()


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def anon_client():
    """未携带凭证的独立客户端。"""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def token(client: TestClient) -> str:
    response = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0, body
    return body["data"]["token"]


@pytest.fixture(scope="module")
def auth(client: TestClient, token: str) -> TestClient:
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def test_health(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"


def test_login_me(auth: TestClient):
    response = auth.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["data"]["user"]["email"] == EMAIL


def test_unauthorized_access(anon_client: TestClient):
    response = anon_client.get("/api/v1/dashboard/overview")
    assert response.status_code == 401
    assert response.json()["code"] == 40101


def test_product_type_crud(auth: TestClient):
    created = auth.post(
        "/api/v1/product-types",
        json={
            "product_type_code": "UV_DTF",
            "display_name": "定制水晶标",
            "prefix": "DZUVDTF",
            "sequence_width": 6,
        },
    )
    assert created.status_code == 200
    assert created.json()["code"] in (0, 40901)

    listed = auth.get("/api/v1/product-types")
    assert listed.json()["code"] == 0
    assert listed.json()["data"]["total"] >= 1

    preview = auth.get("/api/v1/product-types/UV_DTF/next-preview")
    assert preview.json()["code"] == 0
    assert preview.json()["data"]["next_sku"].startswith("DZUVDTF")


def test_batch_create_is_idempotent(auth: TestClient):
    operation_key = new_uuid()
    payload = {
        "operation_key": operation_key,
        "request_key": f"req-{new_uuid()}",
        "product_type_code": "UV_DTF",
        "usage_code": "small_business_packaging",
        "quantity": 2,
        "image_generation_route": "CODEX",
    }
    first = auth.post("/api/v1/batches", json=payload)
    assert first.json()["code"] == 0, first.json()

    second = auth.post("/api/v1/batches", json=payload)
    assert second.json()["code"] == 0, second.json()
    assert second.json()["message"] == "请求已处理（幂等重放）"

    # 不同 operation_key + 同一 request_key + 相同内容 → 业务幂等，返回同一批次
    third = auth.post("/api/v1/batches", json={**payload, "operation_key": new_uuid()})
    assert third.json()["code"] == 0, third.json()
    assert third.json()["data"]["batch"]["id"] == first.json()["data"]["batch"]["id"], third.json()

    # 不同 operation_key + 同一 request_key + 不同内容 → 业务去重拒绝
    fourth = auth.post("/api/v1/batches", json={**payload, "operation_key": new_uuid(), "quantity": 5})
    assert fourth.json()["code"] != 0

    # 同一 operation_key + 不同内容 → 幂等冲突
    fifth = auth.post("/api/v1/batches", json={**payload, "quantity": 7})
    assert fifth.json()["code"] != 0


def test_dashboard_and_guard_endpoints(auth: TestClient):
    assert auth.get("/api/v1/dashboard/overview").json()["code"] == 0
    assert auth.get("/api/v1/guard/status").json()["code"] == 0
    assert auth.get("/api/v1/guard/pauses").json()["code"] == 0
    assert auth.get("/api/v1/guard/claims").json()["code"] == 0
    assert auth.get("/api/v1/images/policy").json()["code"] == 0


def test_review_and_qa_endpoints(auth: TestClient):
    assert auth.get("/api/v1/reviews/pending").json()["code"] == 0
    assert auth.get("/api/v1/qa/false-positive-board").json()["code"] == 0
    assert auth.get("/api/v1/qa/calibration/due").json()["code"] == 0
    assert auth.get("/api/v1/reviews/stats/summary").json()["code"] == 0


def test_validation_error_shape(auth: TestClient):
    response = auth.post("/api/v1/batches", json={"operation_key": "short"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == 40001
    assert body["detail"]
