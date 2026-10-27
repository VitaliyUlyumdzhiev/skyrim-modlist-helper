import asyncio

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app_final
import nexus_client


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("NEXUS_API_KEY", raising=False)
    monkeypatch.setenv("NEXUS_TIMEOUT_SECONDS", "10")

    with app_final.catalog_lock:
        app_final.catalog.clear()
        app_final.catalog.update(app_final.DEMO_MODS)

    with TestClient(app_final.app) as test_client:
        yield test_client

    with app_final.catalog_lock:
        app_final.catalog.clear()
        app_final.catalog.update(app_final.DEMO_MODS)


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version(client):
    response = client.get("/version")

    assert response.status_code == 200
    assert response.json()["version"] == app_final.APP_VERSION


def test_catalog(client):
    response = client.get("/mods")

    assert response.status_code == 200
    assert len(response.json()) == 4


def test_category_filter(client):
    response = client.get(
        "/mods",
        params={"category": "interface"},
    )

    assert response.status_code == 200
    assert [mod["id"] for mod in response.json()] == [12604]


def test_search(client):
    response = client.get(
        "/mods/search",
        params={"q": "skyui"},
    )

    assert response.status_code == 200
    assert response.json()[0]["id"] == 12604


def test_search_without_results(client):
    response = client.get(
        "/mods/search",
        params={"q": "nonexistent-example"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_unknown_mod(client):
    response = client.get("/mods/999999999")

    assert response.status_code == 404


def test_missing_dependency(client):
    response = client.post(
        "/build/check",
        json={"mod_ids": [12604]},
    )

    assert response.status_code == 200
    result = response.json()

    assert result["known_dependencies_satisfied"] is False
    assert result["missing_dependencies"] == [
        {
            "mod_id": 12604,
            "requires_mod_id": 30379,
        }
    ]


def test_dependency_selected(client):
    response = client.post(
        "/build/check",
        json={"mod_ids": [12604, 30379]},
    )

    assert response.status_code == 200
    result = response.json()

    assert result["known_dependencies_satisfied"] is True
    assert result["missing_dependencies"] == []
    assert 30379 in result["unchecked_mod_ids"]


@pytest.mark.parametrize(
    "mod_ids",
    [
        [],
        [-1],
        [0],
        [12604, 12604],
    ],
)
def test_invalid_build(client, mod_ids):
    response = client.post(
        "/build/check",
        json={"mod_ids": mod_ids},
    )

    assert response.status_code == 422


def test_nexus_without_key(client):
    response = client.get("/nexus/mods/12604")

    assert response.status_code == 503


def test_nexus_import_and_search(client, monkeypatch):
    monkeypatch.setenv("NEXUS_API_KEY", "test-key")

    async def fake_fetch(mod_id, api_key, timeout):
        assert mod_id == 123456
        assert api_key == "test-key"

        return {
            "name": "Example Imported Mod",
            "summary": "A mocked response for an automated test",
        }

    monkeypatch.setattr(
        app_final,
        "fetch_nexus_mod",
        fake_fetch,
    )

    response = client.get("/nexus/mods/123456")

    assert response.status_code == 200
    assert response.json()["source"] == "nexus"
    assert response.json()["dependency_data_available"] is False

    search_response = client.get(
        "/mods/search",
        params={"q": "Example Imported"},
    )

    assert search_response.status_code == 200
    assert search_response.json()[0]["id"] == 123456


def test_nexus_http_error_mapping(monkeypatch):
    original_async_client = httpx.AsyncClient

    def handler(request):
        assert request.headers["apikey"] == "test-key"
        return httpx.Response(429)

    transport = httpx.MockTransport(handler)

    def make_client(*args, **kwargs):
        kwargs["transport"] = transport
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(
        nexus_client.httpx,
        "AsyncClient",
        make_client,
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            nexus_client.fetch_nexus_mod(
                mod_id=12604,
                api_key="test-key",
                timeout=10,
            )
        )

    assert error.value.status_code == 503