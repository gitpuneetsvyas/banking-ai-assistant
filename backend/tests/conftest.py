from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.infrastructure.seed import (
    ARJUN_EMAIL,
    ARJUN_PASSWORD,
    PRIYA_EMAIL,
    PRIYA_PASSWORD,
    REVIEWER_EMAIL,
    REVIEWER_PASSWORD,
)
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    settings = Settings(data_dir=tmp_path, jwt_secret="test-secret", llm_provider="deterministic")
    application = create_app(settings)
    with TestClient(application) as test_client:
        yield test_client


def login(client: TestClient, email: str, password: str) -> dict:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def priya(client):
    body = login(client, PRIYA_EMAIL, PRIYA_PASSWORD)
    return auth(body["access_token"])


@pytest.fixture
def arjun(client):
    body = login(client, ARJUN_EMAIL, ARJUN_PASSWORD)
    return auth(body["access_token"])


@pytest.fixture
def reviewer(client):
    body = login(client, REVIEWER_EMAIL, REVIEWER_PASSWORD)
    return auth(body["access_token"])
