from datetime import datetime, timedelta
from math import asinh, floor, radians, tan

from psycopg import Connection
from psycopg.rows import DictRow

from app.core.config import Settings
from app.core.errors import ApiError
from app.routing.comparison import compare_routes, route_options
from app.schemas.assistant import AreaEvidence, ChatRequest, Place, Plan
from app.schemas.heatmap import HeatmapQuery, HeatmapWindow, Methodology
from app.schemas.incident import NearbyIncident, NearbyQuery
from app.schemas.official_zone import ZoneFeature, ZoneProperties, ZoneQuery
from app.schemas.routes import RouteComparisonRequest, RouteQuery
from app.services.geospatial_service import find_nearby_incidents, find_official_zones
from app.services.heatmap_service import HALF_LIFE_DAYS, heatmap, radius_evidence

DB = Connection[DictRow]


def nearby_query(place: Place, request: ChatRequest, plan: Plan) -> NearbyQuery:
    lon, lat = place.point.coordinates
    return NearbyQuery(latitude=lat, longitude=lon, radius_meters=plan.radius_meters, limit=12, mode=request.mode)


def get_nearby_incidents(db: DB, place: Place, request: ChatRequest, plan: Plan, now: datetime):
    end = min(request.end_time, now) if request.end_time else now
    try:
        start = request.start_time or end - timedelta(days=plan.recent_days)
    except OverflowError:
        raise ApiError(422, "invalid_evidence_window", "Choose a more recent date range.") from None
    if not timedelta(0) < end - start <= timedelta(days=90):
        raise ApiError(422, "invalid_evidence_window", "Choose a date range of up to 90 days ending in the past.")
    rows = find_nearby_incidents(db, nearby_query(place, request, plan), eligible_only=True,
                                category=plan.category, start=start, end=end)
    return [NearbyIncident.model_validate(row) for row in rows], HeatmapWindow(start=start, end=end)


def get_official_advisories(db: DB, place: Place, request: ChatRequest, plan: Plan, at: datetime) -> list[ZoneFeature]:
    rows = find_official_zones(db, ZoneQuery(mode=request.mode, at=at.isoformat()), near=nearby_query(place, request, plan))
    return [ZoneFeature(id=row["id"], geometry=row["geometry"], properties=ZoneProperties.model_validate(row)) for row in rows]


def get_area_safety(db: DB, place: Place, request: ChatRequest, plan: Plan, config: Settings, now: datetime) -> AreaEvidence:
    lon, lat = place.point.coordinates
    start = now - timedelta(days=plan.recent_days)
    period = plan.period or request.period or "full_day"
    security, hazards = radius_evidence(
        db, latitude=lat, longitude=lon, radius=plan.radius_meters, is_demo=request.mode == "demo",
        period=period, start=start, end=now, now=now, config=config,
    )
    return AreaEvidence(
        security=security, road_hazards=hazards, radius_meters=plan.radius_meters, generated_at=now,
        window=HeatmapWindow(start=start, end=now), period=period, timezone=config.heatmap_timezone,
        methodology=Methodology(minimum_reports=config.heatmap_min_reports, moderate_threshold=config.heatmap_moderate_threshold,
                                elevated_threshold=config.heatmap_elevated_threshold, half_life_days=HALF_LIFE_DAYS),
    )


def get_heatmap_explanation(db: DB, place: Place, request: ChatRequest, plan: Plan, config: Settings, now: datetime) -> AreaEvidence:
    lon, lat = place.point.coordinates
    if not -85 <= lat <= 85:
        raise ApiError(422, "invalid_map_location", "Choose a point within the map's latitude limits.")
    result = heatmap(db, HeatmapQuery(
        min_lat=lat - .0001, max_lat=lat + .0001, min_lng=max(-180, lon - .0001), max_lng=min(180, lon + .0001),
        mode=request.mode, period=plan.period or request.period or "full_day", cell_size=request.cell_size,
        **{"from": request.start_time.isoformat() if request.start_time else None,
           "to": request.end_time.isoformat() if request.end_time else None},
    ), config, now)
    size = result.cell_size
    x = floor(6378137 * radians(lon) / size)
    y = floor(6378137 * asinh(tan(radians(lat))) / size)
    cell = next((item for item in result.cells.features if item.id == f"{size}:{x}:{y}"), None)
    if cell is None:
        raise ApiError(422, "invalid_map_location", "The selected point is outside the available heatmap grid.")
    return AreaEvidence(
        cell=cell, security=cell.properties.security, road_hazards=cell.properties.road_hazards,
        window=result.window, methodology=result.methodology, generated_at=result.generated_at,
        period=result.period, timezone=result.timezone, cell_size=size,
    )


def get_route_options(db: DB, origin: Place, destination: Place, departure: datetime, config: Settings):
    return route_options(db, RouteQuery(
        origin=",".join(map(str, origin.point.coordinates)), destination=",".join(map(str, destination.point.coordinates)),
        departure_at=departure.isoformat(),
    ), config)


def compare_route_risks(db: DB, route_ids, request: ChatRequest, plan: Plan, config: Settings):
    return compare_routes(db, RouteComparisonRequest(
        route_ids=route_ids, preference=plan.preference, mode=request.mode,
    ), config)
