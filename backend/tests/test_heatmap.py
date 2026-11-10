import asyncio
import os
from datetime import UTC, datetime
from math import atan, degrees, exp, pi
from uuid import uuid4

import httpx
import psycopg
import pytest

from app.core.config import Settings, get_settings
from app.core.database import get_database
from app.main import app
from app.services.heatmap_service import MAX_CELLS, summarize

RADIUS = 6_378_137
SIZE = 750
I, J = 10472, 4590
CELL_ID = f"{SIZE}:{I}:{J}"
DATE = {"from": "2024-01-01T00:00:00Z", "to": "2024-01-07T00:00:00Z"}


def location(dx, dy):
    return (
        degrees((I + dx) * SIZE / RADIUS),
        degrees(2 * atan(exp((J + dy) * SIZE / RADIUS)) - pi / 2),
    )


west, south = location(0.02, 0.02)
east, north = location(0.98, 0.98)
BOUNDS = {"bbox": f"{west},{south},{east},{north}", "cell_size": SIZE, **DATE}


def request(params):
    async def send():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver",
        ) as client:
            return await client.get("/api/heatmap", params=params)
    return asyncio.run(send())


def evidence(response, dimension="security"):
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    cell = next(cell for cell in data["cells"]["features"] if cell["id"] == CELL_ID)
    return cell["properties"][dimension]


@pytest.mark.parametrize(("count", "weight", "band", "coverage", "score"), [
    (0, "0", "grey", "unavailable", None),
    (1, "5", "grey", "limited", None),
    (2, "1.20", "green", "sufficient", 24),
    (2, "1.225", "yellow", "sufficient", 25),
    (3, "3", "red", "sufficient", 60),
    (5, "15", "red", "sufficient", 100),
])
def test_score_boundaries_and_coverage(count, weight, band, coverage, score):
    totals = {"theft": {"count": count, "weight": weight, "latest": "2024-01-01T00:00:00+00:00"}} if count else {}
    result = summarize(totals, Settings(_env_file=None))
    assert (result.band, result.coverage, result.score) == (band, coverage, score)


@pytest.fixture
def no_database():
    app.dependency_overrides[get_database] = lambda: None
    yield
    app.dependency_overrides.pop(get_database, None)


@pytest.mark.parametrize("params", [
    {}, {"bbox": "1,2,3"}, {"bbox": "0,1,0,2"}, {"bbox": "0,1,2,89"},
    {"bbox": "0,1,2,3", "min_lat": 1, "max_lat": 2, "min_lng": 0, "max_lng": 1},
    {"bbox": "0,1,2,3", "cell_size": 10}, {"bbox": "0,1,2,3", "period": "night", "local_hour": 4},
    {"bbox": "0,1,2,3", "from": "2024-01-10T00:00:00Z", "to": "2024-01-01T00:00:00Z"},
    {"bbox": "0,1,2,3", "from": "2023-01-01T00:00:00Z", "to": "2024-01-01T00:00:00Z"},
])
def test_heatmap_request_validation(no_database, params):
    response = request(params)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.fixture
def db():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL for a dedicated PostGIS test database")
    config = Settings(_env_file=None, database_url=url, heatmap_timezone="Asia/Karachi",
                      heatmap_min_reports=2, heatmap_moderate_threshold=25, heatmap_elevated_threshold=60)
    app.dependency_overrides[get_settings] = lambda: config
    inserted = []
    zones = []

    def execute(statement, params=()):
        with psycopg.connect(url, prepare_threshold=None) as connection:
            connection.execute(statement, params)

    def add(*, position=None, severity=1, category="theft", status="corroborated", demo=True,
            summary="Fictional test record", time="2024-01-05T18:15:00Z"):
        incident_id = uuid4()
        longitude, latitude = position or location(0.5, 0.5)
        execute("""
            INSERT INTO public.incidents (
                id, user_id, longitude, latitude, description, public_summary, category,
                occurred_at, severity, verification_status, source, is_demo
            ) VALUES (%s, NULL, %s, %s, 'Private fixture', %s, %s, %s, %s, %s, %s, %s)
        """, (incident_id, longitude, latitude, summary, category, datetime.fromisoformat(time),
              severity, status, "demo" if demo else "community", demo))
        inserted.append(incident_id)
        return incident_id

    def add_zone():
        zone_id = uuid4()
        geometry = f"SRID=4326;MULTIPOLYGON((({west} {south},{east} {south},{east} {north},{west} {north},{west} {south})))"
        execute("""
            INSERT INTO public.official_zones (id, name, description, designation, geometry,
                                              issuing_authority, effective_from, is_demo)
            VALUES (%s, 'Fictional test', 'Fictional test', 'restricted', %s, 'Fictional demo', now(), true)
        """, (zone_id, geometry))
        zones.append(zone_id)

    yield add, execute, add_zone
    app.dependency_overrides.pop(get_settings, None)
    execute("DELETE FROM public.incidents WHERE id = ANY(%s::uuid[])", (inserted,))
    execute("DELETE FROM public.official_zones WHERE id = ANY(%s::uuid[])", (zones,))


def test_empty_and_oversized_viewports(db):
    response = request(BOUNDS)
    data = response.json()["data"]
    assert data["cells"]["type"] == "FeatureCollection"
    assert data["window"] == {"from": "2024-01-01T00:00:00Z", "to": "2024-01-07T00:00:00Z"}
    assert len(data["cells"]["features"]) == 1
    assert evidence(response)["band"] == "grey"
    assert evidence(response)["score"] is None
    oversized = request({"bbox": "-180,-80,180,80"})
    assert oversized.status_code == 422
    assert oversized.json()["error"]["code"] == "viewport_too_large"
    adaptive = request({"bbox": "71.1,30,71.55,30.35", **DATE})
    assert adaptive.status_code == 200
    adaptive_data = adaptive.json()["data"]
    assert adaptive_data["cell_size"] > 750
    assert 0 < len(adaptive_data["cells"]["features"]) <= MAX_CELLS


def test_periods_privacy_and_publication(db):
    add, execute, add_zone = db
    params = {**BOUNDS, "mode": "demo"}
    pending = add(status="pending", summary=None)
    add(status="pending")
    add(status="rejected")
    add(status="verified", summary=None)
    add(demo=False, status="verified")
    add(position=location(2.5, 0.5))
    add(time="2023-12-31T23:59:00Z")
    assert evidence(request(params))["report_count"] == 0
    execute("UPDATE public.incidents SET public_summary = %s WHERE id = %s", ("Reviewed pending fixture", pending))
    assert evidence(request(params))["report_count"] == 0
    execute("UPDATE public.incidents SET verification_status = 'corroborated' WHERE id = %s", (pending,))
    add(time="2024-01-05T22:15:00Z")
    add(time="2024-01-05T03:00:00Z")
    add(time="2024-01-05T14:00:00Z", category="road_accident")
    full = evidence(request(params))
    assert full["report_count"] == 3 and full["category_counts"] == {"theft": 3}
    assert full["latest_report_at"] == "2024-01-05T22:15:00Z"
    assert evidence(request({**params, "period": "night"}))["report_count"] == 2
    assert evidence(request({**params, "period": "morning"}))["report_count"] == 1
    assert evidence(request({**params, "local_hour": 23}))["report_count"] == 1
    assert evidence(request({**params, "period": "evening"}), "road_hazards")["report_count"] == 1
    assert evidence(request(BOUNDS))["report_count"] == 1
    add_zone()
    assert evidence(request(params)) == full


def test_determinism_and_weighting(db):
    add, execute, _ = db
    params = {**BOUNDS, "mode": "demo"}
    longitude, latitude = location(0.5, 0.5)
    first = add()
    second = add()
    baseline = evidence(request(params))
    assert baseline == evidence(request(params))
    assert baseline["score"] is not None
    execute("UPDATE public.incidents SET longitude = %s, latitude = %s WHERE id = %s",
            (round(longitude, 3) + 0.0001, round(latitude, 3) - 0.0001, first))
    assert evidence(request(params)) == baseline
    execute("UPDATE public.incidents SET severity = 2 WHERE id = %s", (first,))
    more_severe = evidence(request(params))["score"]
    assert more_severe > baseline["score"]
    execute("UPDATE public.incidents SET verification_status = 'verified' WHERE id = %s", (first,))
    more_credible = evidence(request(params))["score"]
    assert more_credible > more_severe
    execute("UPDATE public.incidents SET occurred_at = %s WHERE id = %s", (datetime(2024, 1, 1, tzinfo=UTC), second))
    older = evidence(request(params))["score"]
    assert older < more_credible
    far_lng, far_lat = location(0.15, 0.15)
    execute("UPDATE public.incidents SET longitude = %s, latitude = %s WHERE id = %s", (far_lng, far_lat, first))
    farther = evidence(request(params))
    assert farther["report_count"] == 2 and farther["score"] < older
