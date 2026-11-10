import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import psycopg
import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.main import app
from app.routing.provider import fetch_routes
from app.schemas.routes import RouteComparisonRequest, RouteQuery

PARAMS = {"origin": "70.12,29.12", "destination": "70.15,29.12"}
LINE_A = [[70.12, 29.12], [70.135, 29.12], [70.134, 29.12], [70.135, 29.12], [70.15, 29.12]]
LINE_B = [[70.12, 29.12], [70.124, 29.113], [70.146, 29.113], [70.15, 29.12]]


def option(points=LINE_A, distance=3000, duration=300):
    return {"geometry": {"type": "LineString", "coordinates": points}, "distance": distance, "duration": duration}


def mock_provider(monkeypatch, routes=None, *, code="Ok", status=200, fail=False):
    def get(url, **kwargs):
        assert "/route/v1/driving/70.120000,29.120000;70.150000,29.120000" in url
        assert kwargs["params"]["geometries"] == "geojson"
        assert kwargs["params"]["alternatives"] == 2
        if fail:
            raise httpx.ReadTimeout("private provider details")
        return httpx.Response(status, json={"code": code, "routes": routes or []},
                              request=httpx.Request("GET", url))
    monkeypatch.setattr("app.routing.provider.httpx.get", get)


@pytest.mark.parametrize("values", [
    {"origin": "500,0"}, {"origin": "70.12,NaN"}, {"origin": "70.12"},
    {"destination": PARAMS["origin"]}, {"destination": "0,0"}, {"alternatives": 4},
    {"departure_at": "2024-01-01"}, {"departure_at": "2024-01-01T00:00:00Z"},
])
def test_invalid_route_queries(values):
    with pytest.raises(ValidationError):
        RouteQuery(**{**PARAMS, **values})


def test_route_reference_limits():
    id = str(uuid4())
    with pytest.raises(ValidationError):
        RouteComparisonRequest(route_ids=[id, id])


def test_osrm_geometry_and_one_route(monkeypatch):
    mock_provider(monkeypatch, [option(), option()])
    config = Settings(_env_file=None, routing_service_url="https://route.example.test")
    routes = fetch_routes(RouteQuery(**PARAMS), config)
    assert len(routes) == 1 and routes[0].geometry.coordinates[1] == (70.135, 29.12)
    assert (routes[0].distance_m, routes[0].duration_s) == (3000, 300)


@pytest.mark.parametrize(("case", "expected"), [("timeout", 503), ("provider", 503), ("geometry", 502), ("unrelated", 502)])
def test_routing_provider_failures(monkeypatch, case, expected):
    routes = [option([[0, 0], [0, 1]])] if case == "unrelated" else [option([[70.12, 29.12]])]
    mock_provider(monkeypatch, routes, status=503 if case == "provider" else 200, fail=case == "timeout")
    with pytest.raises(ApiError) as failure:
        fetch_routes(RouteQuery(**PARAMS), Settings(_env_file=None, routing_service_url="https://route.example.test"))
    assert failure.value.status_code == expected


def test_no_route_and_unconfigured(monkeypatch):
    mock_provider(monkeypatch, code="NoRoute", status=400)
    assert fetch_routes(RouteQuery(**PARAMS), Settings(_env_file=None, routing_service_url="https://route.example.test")) == []
    with pytest.raises(ApiError, match="configured"):
        fetch_routes(RouteQuery(**PARAMS), Settings(_env_file=None, routing_service_url=None))


def request(method, path, **kwargs):
    async def send():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)
    return asyncio.run(send())


@pytest.fixture
def demo():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL for a dedicated PostGIS database")
    config = Settings(_env_file=None, database_url=url, routing_service_url="https://route.example.test",
                      heatmap_min_reports=2)
    app.dependency_overrides[get_settings] = lambda: config
    incidents, zones, routes = [], [], []

    def execute(statement, params=()):
        with psycopg.connect(url, prepare_threshold=None) as connection:
            connection.execute(statement, params)

    def add_report(status="corroborated", summary="Fictional fixture", category="theft", lat=29.12):
        id = uuid4()
        incidents.append(id)
        execute("""
            INSERT INTO public.incidents
              (id, category, latitude, longitude, occurred_at, description, public_summary,
               severity, verification_status, source, is_demo)
            VALUES (%s, %s, %s, 70.135, now() - interval '1 hour', 'Fictional fixture', %s,
                    4, %s, 'demo', true)
        """, (id, category, lat, summary, status))

    def add_zone(start, end=None):
        id = uuid4()
        zones.append(id)
        geometry = "SRID=4326;MULTIPOLYGON(((70.133 29.119,70.138 29.119,70.138 29.121,70.133 29.121,70.133 29.119)))"
        execute("""
            INSERT INTO public.official_zones
              (id, name, description, designation, geometry, issuing_authority, effective_from, effective_until, is_demo)
            VALUES (%s, 'Fictional route closure', 'Fictional fixture', 'road_closure', %s, 'Fictional demo', %s, %s, true)
        """, (id, geometry, start, end))
        return str(id)

    def get_options(departure):
        response = request("GET", "/api/routes", params={**PARAMS, "departure_at": departure.isoformat()})
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        ids = [route["id"] for route in response.json()["data"]["routes"]]
        routes.extend(ids)
        return ids

    yield add_report, add_zone, get_options, execute
    app.dependency_overrides.pop(get_settings, None)
    execute("DELETE FROM public.incidents WHERE id = ANY(%s::uuid[])", (incidents,))
    execute("DELETE FROM public.official_zones WHERE id = ANY(%s::uuid[])", (zones,))
    execute("DELETE FROM public.route_references WHERE id = ANY(%s::uuid[])", (routes,))


def test_compares_routes_with_eligible_exposure_and_advisory_overlap(demo, monkeypatch):
    add_report, add_zone, get_options, _ = demo
    departure = datetime.now(UTC)
    for _ in range(2):
        add_report()
    add_report(category="road_accident")
    add_report(status="pending")
    add_report(status="rejected")
    add_report(status="verified", summary=None)
    add_report(lat=29.13)
    active = add_zone(departure + timedelta(minutes=2))
    add_zone(departure - timedelta(hours=2), departure - timedelta(hours=1))
    add_zone(departure + timedelta(hours=1))
    mock_provider(monkeypatch, [option(), option(LINE_B, 4100, 490)])
    ids = get_options(departure)
    assert len(ids) == 2
    response = request("POST", "/api/routes/compare", json={"route_ids": ids, "mode": "demo"})
    assert response.status_code == 200, response.text
    safe_rank, closure_rank = response.json()["data"]["routes"]
    assert safe_rank["id"] == ids[1] and closure_rank["id"] == ids[0]
    assert closure_rank["security"]["report_count"] == 2
    assert 0 < closure_rank["security"]["score"] < 100
    assert closure_rank["road_hazards"]["report_count"] == 1
    assert closure_rank["road_hazards"]["score"] is None
    assert [zone["id"] for zone in closure_rank["official_zones"]] == [active]
    assert safe_rank["security"]["band"] == "grey" and safe_rank["official_coverage"] == "unavailable"
    live = request("POST", "/api/routes/compare", json={"route_ids": ids, "mode": "live"}).json()["data"]
    assert all(route["security"]["report_count"] == 0 and not route["official_zones"] for route in live["routes"])


def test_expired_or_mixed_route_references(demo, monkeypatch):
    _, _, get_options, execute = demo
    mock_provider(monkeypatch, [option()])
    first = get_options(datetime.now(UTC))
    other = get_options(datetime.now(UTC))
    assert request("POST", "/api/routes/compare", json={"route_ids": first + other}).status_code == 404
    execute("UPDATE public.route_references SET expires_at = now() - interval '1 second' WHERE id = %s", (first[0],))
    assert request("POST", "/api/routes/compare", json={"route_ids": first}).status_code == 404
