import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest

from app.core import security
from app.core.config import Settings, get_settings
from app.core.database import get_database
from app.main import app
from app.schemas.incident import IncidentQuery, PublicIncident
from app.services.geospatial_service import count_incidents_by_category, distance_between_points, incident_feature

DEMO_INCIDENT = "b674f9e1-27c4-42f0-82d8-c87a31323e04"
DEMO_ZONE = "b674f9e1-27c4-42f0-82d8-c87a31323e08"
TEST_TOKEN = {"Authorization": "Bearer test-token"}
BOUNDS = {"min_lat": 30.194, "max_lat": 30.196, "min_lng": 71.474, "max_lng": 71.476}


def request(method, path, **kwargs):
    async def send():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver",
        ) as client:
            return await client.request(method, f"/api{path}", **kwargs)

    return asyncio.run(send())


@pytest.fixture
def incident():
    return {
        "category": "robbery",
        "description": f"Private test report {uuid4()}. '); DROP TABLE incidents; --",
        "latitude": 30.195321,
        "longitude": 71.475432,
        "occurred_at": (datetime.now(UTC) - timedelta(minutes=10)).isoformat(),
    }


@pytest.fixture
def config():
    overrides = app.dependency_overrides.copy()
    settings = Settings(_env_file=None, supabase_url="https://auth.example.test", supabase_anon_key="test-key")
    settings.database_url = None
    app.dependency_overrides[get_settings] = lambda: settings
    yield settings
    app.dependency_overrides.clear()
    app.dependency_overrides.update(overrides)


@pytest.fixture
def mock_auth(monkeypatch):
    def setup(user_id, *, status=200, anonymous=False):
        def get(url, *, headers, timeout):
            assert url == "https://auth.example.test/auth/v1/user"
            assert headers == {"apikey": "test-key", "Authorization": "Bearer test-token"}
            assert timeout == 5
            return httpx.Response(status, json={"id": str(user_id), "is_anonymous": anonymous})

        monkeypatch.setattr(security.httpx, "get", get)

    return setup


@pytest.fixture
def isolated(config, mock_auth):
    mock_auth(uuid4())
    app.dependency_overrides[get_database] = lambda: None


def test_authentication_required(config, incident):
    response = request("POST", "/incidents", json=incident)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(("status", "anonymous", "expected"), [(401, False, 401), (200, True, 403), (500, False, 503)])
def test_invalid_or_unavailable_auth(config, mock_auth, incident, status, anonymous, expected):
    mock_auth(uuid4(), status=status, anonymous=anonymous)
    response = request("POST", "/incidents", headers=TEST_TOKEN, json=incident)
    assert response.status_code == expected
    assert response.json()["data"] is None


@pytest.mark.parametrize("path", ["/incidents", "/ready"])
def test_missing_database_config(config, path):
    response = request("GET", path)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"


@pytest.mark.parametrize("change", [
    {"latitude": 90.001}, {"longitude": -180.001}, {"longitude": "71.475432"},
    {"category": "robbery'; DROP TABLE incidents; --"}, {"description": "   "},
    {"description": "a" * 2001}, {"description": "a\x00b"},
    {"occurred_at": "2999-01-01T00:00:00Z"}, {"occurred_at": "2020-01-01T00:00:00"},
    {"user_id": str(uuid4())}, {"verification_status": "verified"},
    {"severity": 5}, {"credibility_score": 1}, {"is_demo": True}, {"public_summary": "Publish immediately"},
])
def test_invalid_submission(isolated, incident, change):
    response = request("POST", "/incidents", headers=TEST_TOKEN, json={**incident, **change})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize(("path", "params"), [
    ("/incidents", {"min_lat": 30}),
    ("/incidents", {**BOUNDS, "min_lng": 72}),
    ("/incidents", {"limit": 101}),
    ("/incidents", {"start_time": "2020-01-01T00:00:00Z", "end_time": "2019-01-01T00:00:00Z"}),
    ("/incidents/nearby", {"latitude": 30, "longitude": 71, "radius_meters": 5001}),
    ("/official-zones", {"max_lng": 71}),
])
def test_invalid_read_filters(isolated, path, params):
    response = request("GET", path, params=params)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.fixture
def db(config, mock_auth):
    url = os.getenv("TEST_DATABASE_URL")
    user_id = os.getenv("TEST_AUTH_USER_ID")
    if not url or not user_id:
        pytest.skip("Set TEST_DATABASE_URL and TEST_AUTH_USER_ID for a dedicated seeded test database")
    config.database_url = Settings(database_url=url).database_url
    mock_auth(UUID(user_id))
    return config, UUID(user_id)


@pytest.fixture
def created(db, incident):
    config, user_id = db
    response = request("POST", "/incidents", headers=TEST_TOKEN, json=incident)
    assert response.status_code == 201, response.json()
    data = response.json()["data"]
    record_id = UUID(data["id"])
    try:
        yield config, user_id, record_id, data
    finally:
        with psycopg.connect(config.database_url.get_secret_value(), prepare_threshold=None) as connection:
            connection.execute("DELETE FROM public.incidents WHERE id = %s", (record_id,))


def test_submission_persists_and_public_reads_respect_moderation(created, incident):
    config, user_id, record_id, data = created
    assert data["verification_status"] == "pending"
    assert data["severity"] == 1
    assert data["source"] == "community"
    assert data["is_demo"] is False
    assert data["public_summary"] is None
    assert data["location"] == {"type": "Point", "coordinates": [71.475, 30.195]}
    assert {"user_id", "description", "credibility_score", "evidence_url"}.isdisjoint(data)
    assert request("GET", f"/incidents/{record_id}").status_code == 404

    url = config.database_url.get_secret_value()
    with psycopg.connect(url, prepare_threshold=None) as connection:
        row = connection.execute("""
            SELECT user_id, description, latitude, longitude, credibility_score FROM public.incidents WHERE id = %s
        """, (record_id,)).fetchone()
        assert row == (user_id, incident["description"], incident["latitude"], incident["longitude"], 0)
        connection.execute(
            "UPDATE public.incidents SET public_summary = %s WHERE id = %s", ("Reviewed public summary.", record_id)
        )

    detail = request("GET", f"/incidents/{record_id}")
    assert detail.status_code == 200
    item = detail.json()["data"]
    assert item["public_summary"] == "Reviewed public summary."
    assert item["verification_status"] == "pending"
    assert {"user_id", "description", "credibility_score", "evidence_url"}.isdisjoint(item)

    def ids(path, params):
        result = request("GET", path, params=params)
        assert result.status_code == 200, result.json()
        return {row["id"]: row for row in result.json()["data"]["items"]}

    assert str(record_id) in ids("/incidents", {**BOUNDS, "category": "robbery", "verification_status": "pending"})
    assert str(record_id) not in ids("/incidents", {**BOUNDS, "category": "theft"})
    assert str(record_id) not in ids("/incidents", {**BOUNDS, "min_lat": 30.199, "max_lat": 30.200})
    assert str(record_id) not in ids("/incidents", {**BOUNDS, "start_time": datetime.now(UTC).isoformat()})
    nearby = {"latitude": 30.195, "longitude": 71.475, "radius_meters": 100}
    assert ids("/incidents/nearby", nearby)[str(record_id)]["distance_meters"] == 0
    assert str(record_id) not in ids("/incidents/nearby", {**nearby, "longitude": 71.490})
    assert str(record_id) not in ids("/incidents", {**BOUNDS, "mode": "demo"})

    database = get_database(config)
    db = next(database)
    try:
        assert count_incidents_by_category(db, IncidentQuery(**BOUNDS, category="robbery"))["robbery"] >= 1
        assert 90 < distance_between_points(db, (71.475, 30.195), (71.476, 30.195)) < 110
        assert incident_feature(PublicIncident.model_validate(item))["geometry"] == item["location"]
    finally:
        database.close()

    with psycopg.connect(url, prepare_threshold=None) as connection:
        connection.execute("UPDATE public.incidents SET verification_status = 'rejected' WHERE id = %s", (record_id,))
    assert request("GET", f"/incidents/{record_id}").status_code == 404
    assert str(record_id) not in ids("/incidents", {**BOUNDS, "verification_status": "rejected"})
    assert str(record_id) not in ids("/incidents/nearby", nearby)


def test_demo_incidents_and_zones_are_segregated(db):
    assert request("GET", f"/incidents/{DEMO_INCIDENT}").status_code == 404
    incident_response = request("GET", f"/incidents/{DEMO_INCIDENT}", params={"mode": "demo"})
    assert incident_response.status_code == 200
    assert incident_response.json()["data"]["is_demo"] is True

    params = {"mode": "demo", "min_lat": 30.188, "max_lat": 30.192, "min_lng": 71.475, "max_lng": 71.479}
    response = request("GET", "/official-zones", params=params)
    assert response.status_code == 200, response.json()
    collection = response.json()["data"]
    assert collection["type"] == "FeatureCollection"
    feature = next(item for item in collection["features"] if item["id"] == DEMO_ZONE)
    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "MultiPolygon"
    assert feature["geometry"]["coordinates"][0][0][0] == [71.476, 30.189]
    assert feature["properties"]["is_demo"] is True
    assert feature["properties"]["issuing_authority"] == "Fictional demo"
    assert feature["properties"]["source_url"] is None

    before = {**params, "at": "2000-01-01T00:00:00Z"}
    assert request("GET", "/official-zones", params=before).json()["data"]["features"] == []
    all_dates = request("GET", "/official-zones", params={**before, "active_only": "false"}).json()["data"]
    assert any(item["id"] == DEMO_ZONE for item in all_dates["features"])
    assert request("GET", "/official-zones", params={**params, "min_lng": 71.480, "max_lng": 71.482}).json()["data"]["features"] == []
    live = request("GET", "/official-zones", params={**params, "mode": "live"}).json()["data"]
    assert all(item["id"] != DEMO_ZONE and not item["properties"]["is_demo"] for item in live["features"])


def test_fictional_review_enters_only_demo_heatmap(created):
    config, _, record_id, _ = created
    assert request("GET", "/ready").status_code == 200
    assert request("GET", f"/incidents/{record_id}").status_code == 404
    assert request("GET", f"/incidents/{record_id}", params={"mode": "demo"}).status_code == 404

    def total(mode):
        response = request("GET", "/heatmap", params={**BOUNDS, "cell_size": 750, "mode": mode})
        assert response.status_code == 200, response.json()
        cells = response.json()["data"]["cells"]["features"]
        return sum(cell["properties"]["security"]["report_count"] for cell in cells)

    live, demo = total("live"), total("demo")
    with psycopg.connect(config.database_url.get_secret_value(), prepare_threshold=None) as connection:
        connection.execute("""
            UPDATE public.incidents
            SET verification_status = 'corroborated', source = 'demo', is_demo = true,
                user_id = NULL, public_summary = 'Fictional QA report after authorized review'
            WHERE id = %s AND verification_status = 'pending'
        """, (record_id,))
        connection.execute("SET LOCAL ROLE anon")
        assert connection.execute("SELECT id FROM public.incidents WHERE id = %s", (record_id,)).fetchone() is None

    assert request("GET", f"/incidents/{record_id}").status_code == 404
    reviewed = request("GET", f"/incidents/{record_id}", params={"mode": "demo"}).json()["data"]
    assert reviewed["verification_status"] == "corroborated"
    assert total("demo") == demo + 1 and total("live") == live


def test_report_rate_limit_and_direct_write_privileges(db, incident):
    config, user_id = db
    identifiers = [uuid4() for _ in range(10)]
    url = config.database_url.get_secret_value()
    try:
        with psycopg.connect(url, prepare_threshold=None) as connection:
            connection.execute("INSERT INTO public.profiles (id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
            connection.execute("""
                INSERT INTO public.incidents (id, user_id, category, description, latitude, longitude, occurred_at)
                SELECT unnest(%s::uuid[]), %s, 'other', 'Private QA rate limit fixture', 30, 71, now() - interval '1 minute'
            """, (identifiers, user_id))
            assert connection.execute("""
                SELECT has_column_privilege('authenticated', 'public.incidents', 'description', 'INSERT')
                    OR has_column_privilege('authenticated', 'public.incidents', 'latitude', 'SELECT')
                    OR has_column_privilege('authenticated', 'public.incidents', 'verification_status', 'UPDATE')
            """).fetchone() == (False,)
        response = request("POST", "/incidents", headers=TEST_TOKEN, json=incident)
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "incident_rate_limited"
    finally:
        with psycopg.connect(url, prepare_threshold=None) as connection:
            connection.execute("DELETE FROM public.incidents WHERE id = ANY(%s::uuid[])", (identifiers,))
