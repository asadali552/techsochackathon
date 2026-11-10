import asyncio

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings

from app.main import app, settings


async def get_health(origin: str | None = None) -> httpx.Response:
    headers = {"Origin": origin} if origin else {}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        return await client.get("/api/health", headers=headers)


def test_health_returns_expected_envelope():
    response = asyncio.run(get_health())

    assert response.status_code == 200
    assert response.json() == {"data": {"status": "ok"}, "error": None}


def test_configured_frontend_can_read_health():
    for origin in settings.cors_origins:
        response = asyncio.run(get_health(origin))

        assert response.headers["access-control-allow-origin"] == origin

    unlisted_origin = "https://unlisted.example"
    while unlisted_origin in settings.cors_origins:
        unlisted_origin = unlisted_origin.replace("://", "://unlisted.", 1)
    response = asyncio.run(get_health(unlisted_origin))

    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("value", ["*", "https://*.example.com", "https://example.com/", "https://name@example.com"])
def test_cors_config_rejects_wildcards_and_non_origins(value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=[value])


@pytest.mark.parametrize("path", ["/api/routes", "/api/incidents/nearby"])
def test_location_queries_are_omitted_from_access_logs(path):
    import logging
    from app.routing.provider import PrivateLocationLogs

    message = '%s - "%s %s HTTP/%s" %s'
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, message,
                               ("client", "GET", path + "?latitude=30.190001", "1.1", 200), None)
    assert PrivateLocationLogs().filter(record)
    assert path in record.getMessage()
    assert "30.190001" not in record.getMessage()
