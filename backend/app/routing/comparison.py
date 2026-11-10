from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from psycopg import Connection, sql
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from app.core.config import Settings
from app.core.errors import ApiError
from app.routing.provider import fetch_routes
from app.schemas.official_zone import ZoneFeature, ZoneProperties
from app.schemas.routes import ComparedRoute, Route, RouteComparison, RouteComparisonRequest, RouteList, RouteQuery
from app.services.geospatial_service import PUBLIC_REPORTS
from app.services.heatmap_service import HALF_LIFE_DAYS, ROAD_CATEGORIES, summarize

CORRIDOR_M = 250
EVIDENCE_DAYS = 30
VERSION = "route-exposure-v1"

EXPOSURE = sql.SQL("""
    WITH path AS (SELECT ST_GeomFromGeoJSON(%(geometry)s::jsonb)::geography AS line)
    SELECT category, count(*) AS count, max(occurred_at) AS latest,
           sum(round((
               coalesce(severity, 1) * CASE verification_status WHEN 'verified' THEN 1.0 ELSE 0.75 END
               * POWER(2.0, -extract(epoch FROM (%(evidence_end)s - occurred_at)) / (%(half_life)s * 86400.0))
               * greatest(0.25, 1.0 - 0.75 * ST_Distance(public_location, line) / %(corridor)s)
           )::numeric, 6)) AS weight
    FROM public.incidents CROSS JOIN path
    WHERE {visible} AND verification_status IN ('corroborated', 'verified')
      AND occurred_at >= %(evidence_start)s AND occurred_at < %(evidence_end)s
      AND ST_DWithin(public_location, line, %(corridor)s)
    GROUP BY category
""").format(visible=PUBLIC_REPORTS)

ZONES = """
    WITH path AS (SELECT ST_GeomFromGeoJSON(%(geometry)s::jsonb) AS line)
    SELECT id, name, description, designation, issuing_authority, source_url, source_reference,
           effective_from, effective_until, last_verified_at, is_demo,
           ST_AsGeoJSON(geometry::geometry)::json AS geometry
    FROM public.official_zones CROSS JOIN path
    WHERE is_demo = %(is_demo)s AND (revoked_at IS NULL OR revoked_at > greatest(effective_from, %(departure)s))
      AND effective_from <= %(arrival)s
      AND (effective_until IS NULL OR effective_until > %(departure)s)
      AND ST_Intersects(geometry::geometry, line)
    ORDER BY CASE designation WHEN 'restricted' THEN 0 WHEN 'road_closure' THEN 1 ELSE 2 END, id
    LIMIT 50
"""


def route_options(db: Connection[DictRow], query: RouteQuery, config: Settings) -> RouteList:
    departure = query.departure_at or datetime.now(UTC)
    lines = fetch_routes(query, config)
    routes = [Route(id=uuid4(), **line.model_dump()) for line in lines]
    trip = uuid4()
    db.execute("DELETE FROM public.route_references WHERE expires_at <= now()")
    for route in routes:
        db.execute("""
            INSERT INTO public.route_references (id, trip_id, departure_at, expires_at, route)
            VALUES (%s, %s, %s, clock_timestamp() + interval '15 minutes', %s)
        """, (route.id, trip, departure, Jsonb(route.model_dump(mode="json"))))
    return RouteList(routes=routes, departure_at=departure, provider="OSRM")


def compare_routes(db: Connection[DictRow], query: RouteComparisonRequest, config: Settings) -> RouteComparison:
    rows = db.execute("""
        SELECT id, trip_id, departure_at, route FROM public.route_references
        WHERE id = ANY(%s::uuid[]) AND expires_at > now()
    """, (query.route_ids,)).fetchall()
    if len(rows) != len(query.route_ids) or len({row["trip_id"] for row in rows}) != 1:
        raise ApiError(404, "routes_expired", "Find routes again before comparing them")

    by_id = {row["id"]: row for row in rows}
    departure = rows[0]["departure_at"]
    evidence_end = min(departure, datetime.now(UTC))
    compared = []
    for route_id in query.route_ids:
        route = Route.model_validate(by_id[route_id]["route"])
        params = {
            "geometry": Jsonb(route.geometry.model_dump(mode="json")),
            "is_demo": query.mode == "demo",
            "evidence_start": evidence_end - timedelta(days=EVIDENCE_DAYS),
            "evidence_end": evidence_end, "half_life": HALF_LIFE_DAYS, "corridor": CORRIDOR_M,
            "departure": departure, "arrival": departure + timedelta(seconds=route.duration_s),
        }
        per_km = Decimal(str(max(1, route.distance_m / 1000)))
        categories = {
            row["category"]: {"count": row["count"], "weight": str(row["weight"] / per_km), "latest": row["latest"].isoformat()}
            for row in db.execute(EXPOSURE, params).fetchall()
        }
        security = summarize({k: v for k, v in categories.items() if k not in ROAD_CATEGORIES}, config)
        hazards = summarize({k: v for k, v in categories.items() if k in ROAD_CATEGORIES}, config)
        zones = [
            ZoneFeature(id=row["id"], geometry=row["geometry"], properties=ZoneProperties.model_validate(row))
            for row in db.execute(ZONES, params).fetchall()
        ]
        restrictions = sum(zone.properties.designation in ("restricted", "road_closure") for zone in zones)
        trade_offs = [
            f"{security.report_count} eligible safety reports and {hazards.report_count} road-hazard reports within {CORRIDOR_M} m.",
            f"{restrictions} stored restrictions or closures intersect this route." if restrictions
            else "No stored restriction or closure matched. Advisory coverage may be incomplete.",
        ]
        if security.coverage != "sufficient" or hazards.coverage != "sufficient":
            trade_offs.append("Evidence is limited. Use travel estimates and reported conditions together.")
        compared.append(ComparedRoute(
            **route.model_dump(), security=security, road_hazards=hazards, official_zones=zones,
            official_coverage="available" if zones else "unavailable", trade_offs=trade_offs,
        ))

    if query.preference == "shortest":
        compared.sort(key=lambda item: item.distance_m)
    elif query.preference == "fastest":
        compared.sort(key=lambda item: item.duration_s)
    elif query.preference == "fewer_reported_incidents":
        compared.sort(key=lambda item: (
            item.security.score is None, item.security.report_count / max(1, item.distance_m / 1000), item.duration_s,
        ))
    else:
        compared.sort(key=lambda item: (
            any(zone.properties.designation in ("restricted", "road_closure") for zone in item.official_zones),
            item.duration_s,
        ))
    return RouteComparison(
        routes=compared, preference=query.preference, mode=query.mode, scoring_version=VERSION,
        corridor_m=CORRIDOR_M, evidence_window_days=EVIDENCE_DAYS, departure_at=departure,
    )
