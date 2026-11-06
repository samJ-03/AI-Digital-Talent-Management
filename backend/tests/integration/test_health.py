"""平台开发工具：验证health的正常与失败场景；测试数据仅用于隔离环境。"""
import json
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
import pytest
from app.main import create_app
from app.core.settings import Settings

SECRET = "TEST_ONLY_DO_NOT_EXPOSE_0123456789"

@pytest.fixture
def app():
    settings = Settings(environment="test", database_url="mysql+pymysql://user:"+SECRET+"@mysql/talent", redis_url="redis://redis:6379/0", monitor_token=SECRET)
    return create_app(settings)

@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


def test_health_no_secrets(client):
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == {"alive": True}
    assert data["request_id"] == response.headers["x-request-id"]
    assert SECRET not in json.dumps(data)
    assert "mysql" not in json.dumps(data)


def test_readiness_is_restricted(client):
    assert client.get("/api/v1/health/ready").status_code == 401
    assert client.get("/api/v1/health/ready", headers={"X-Monitor-Token":"wrong"}).status_code == 401


def test_ready_requires_db_and_redis(app, client):
    app.state.readiness_probe = lambda: {"mysql": True, "redis": False}
    response = client.get("/api/v1/health/ready", headers={"X-Monitor-Token":SECRET})
    assert response.status_code == 503
    assert response.json()["data"]["ready"] is False
    assert response.json()["data"]["dependencies"] == {"mysql": True, "redis": False}


def test_ready_after_both_protocol_checks(app, client):
    app.state.readiness_probe = lambda: {"mysql": True, "redis": True}
    response = client.get("/api/v1/health/ready", headers={"X-Monitor-Token":SECRET})
    assert response.status_code == 200
    assert response.json()["data"]["ready"] is True


def test_readiness_exception_no_secret(app, client):
    def failed():
        raise RuntimeError(SECRET)
    app.state.readiness_probe = failed
    response = client.get("/api/v1/health/ready", headers={"X-Monitor-Token":SECRET})
    assert response.status_code == 503
    assert SECRET not in response.text


def test_error_envelope_validation(app, client):
    class Input(BaseModel):
        count: int = Field(ge=1)
    @app.post("/_test/validation")
    def validation(body: Input):
        return body
    response = client.post("/_test/validation", json={"count":SECRET})
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_INPUT"
    assert response.json()["request_id"]
    assert SECRET not in response.text


def test_error_envelope_unexpected(app, client):
    @app.get("/_test/failure")
    def failure():
        raise RuntimeError(SECRET)
    response = client.get("/_test/failure")
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert response.json()["request_id"]
    assert SECRET not in response.text


def test_malformed_request_id_replaced(client):
    response = client.get("/api/v1/health/live", headers={"X-Request-ID":"not-a-valid-id"})
    from uuid import UUID
    UUID(response.headers["x-request-id"])


def test_valid_request_id_preserved(client):
    request_id = "e2306cc0-7234-4642-a2cb-c608ce083c16"
    response = client.get("/api/v1/health/live", headers={"X-Request-ID":request_id})
    assert response.headers["x-request-id"] == request_id


def test_production_requires_strong_monitor_token():
    with pytest.raises(ValueError):
        Settings(environment="production", database_url="mysql+pymysql://user:test@mysql/talent", redis_url="redis://redis:6379/0", monitor_token="short")
