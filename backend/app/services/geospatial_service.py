from datetime import UTC, datetime

from psycopg import Connection, sql
from psycopg.rows import DictRow

from app.schemas.common import Bounds, Mode
from app.schemas.incident import IncidentQuery, NearbyQuery, PublicIncident
from app.schemas.official_zone import ZoneQuery

INCIDENT_FIELDS = sql.SQL("""
    id, category, public_summary, ST_AsGeoJSON(public_location::geometry)::json AS location,
    occurred_at, created_at, severity, verification_status, source, is_demo
""")
PUBLIC_REPORTS = sql.SQL("""
    is_demo = %(is_demo)s AND public_summary IS NOT NULL AND verification_status <> 'rejected'
""")
ENVELOPE = sql.SQL("ST_MakeEnvelope(%(min_lng)s, %(min_lat)s, %(max_lng)s, %(max_lat)s, 4326)")
POINT = sql.SQL("ST_SetSRID(ST_MakePoint(%(longitude)s, %(latitude)s), 4326)::geography")
BOUND_FIELDS = {"min_lat", "max_lat", "min_lng", "max_lng"}


def bounds_params(bounds: Bounds) -> dict:
    return bounds.model_dump(include=BOUND_FIELDS, exclude_none=True)


def incident_filters(query: IncidentQuery) -> tuple[sql.Composed, dict]:
    predicates = [PUBLIC_REPORTS]
    params = query.model_dump(exclude_none=True, exclude={"mode", "limit", "offset"})
    params["is_demo"] = query.mode == "demo"
    if query.min_lat is not None:
        predicates.append(sql.SQL("public_location::geometry && {}").format(ENVELOPE))
    if query.category is not None:
        predicates.append(sql.SQL("category = %(category)s"))
    if query.verification_status is not None:
        predicates.append(sql.SQL("verification_status = %(verification_status)s"))
    if query.start_time is not None:
        predicates.append(sql.SQL("occurred_at >= %(start_time)s"))
    if query.end_time is not None:
        predicates.append(sql.SQL("occurred_at < %(end_time)s"))
    return sql.SQL(" AND ").join(predicates), params


def find_incidents_in_bounds(db: Connection[DictRow], query: IncidentQuery) -> list[DictRow]:
    filters, params = incident_filters(query)
    statement = sql.SQL("""
        SELECT {fields} FROM public.incidents WHERE {filters}
        ORDER BY occurred_at DESC, id DESC LIMIT %(limit)s OFFSET %(offset)s
    """).format(fields=INCIDENT_FIELDS, filters=filters)
    return db.execute(statement, {**params, "limit": query.limit, "offset": query.offset}).fetchall()


def find_nearby_incidents(
    db: Connection[DictRow], query: NearbyQuery, *, eligible_only: bool = False,
    category: str | None = None, start: datetime | None = None, end: datetime | None = None,
) -> list[DictRow]:
    predicates = [PUBLIC_REPORTS]
    if eligible_only:
        predicates.append(sql.SQL("verification_status IN ('corroborated', 'verified')"))
    if category is not None:
        predicates.append(sql.SQL("category = %(category)s"))
    if start is not None:
        predicates.append(sql.SQL("occurred_at >= %(start)s"))
    if end is not None:
        predicates.append(sql.SQL("occurred_at < %(end)s"))
    statement = sql.SQL("""
        SELECT {fields}, ST_Distance(public_location, {point}) AS distance_meters
        FROM public.incidents
        WHERE {visible} AND ST_DWithin(public_location, {point}, %(radius_meters)s)
        ORDER BY distance_meters, id LIMIT %(limit)s
    """).format(fields=INCIDENT_FIELDS, point=POINT, visible=sql.SQL(" AND ").join(predicates))
    params = query.model_dump(exclude={"mode"})
    return db.execute(statement, {
        **params, "is_demo": query.mode == "demo", "category": category, "start": start, "end": end,
    }).fetchall()


def count_incidents_by_category(db: Connection[DictRow], query: IncidentQuery) -> dict[str, int]:
    filters, params = incident_filters(query)
    statement = sql.SQL("""
        SELECT category, count(*) AS count FROM public.incidents
        WHERE {} GROUP BY category
    """).format(filters)
    return {row["category"]: row["count"] for row in db.execute(statement, params)}


def find_official_zones(
    db: Connection[DictRow], query: ZoneQuery, *, near: NearbyQuery | None = None,
) -> list[DictRow]:
    predicates = [sql.SQL("is_demo = %(is_demo)s AND revoked_at IS NULL")]
    params = {"is_demo": query.mode == "demo", **bounds_params(query)}
    if query.active_only:
        predicates.append(sql.SQL("effective_from <= %(at)s AND (effective_until IS NULL OR effective_until > %(at)s)"))
        params["at"] = query.at or datetime.now(UTC)
    if query.min_lat is not None:
        predicates.append(sql.SQL("ST_Intersects(geometry::geometry, {})").format(ENVELOPE))
    if near is not None:
        predicates.append(sql.SQL("ST_DWithin(geometry, {}, %(radius_meters)s)").format(POINT))
        params.update(latitude=near.latitude, longitude=near.longitude, radius_meters=near.radius_meters)
    statement = sql.SQL("""
        SELECT id, name, description, designation, issuing_authority, source_url, source_reference,
               effective_from, effective_until, last_verified_at, is_demo,
               ST_AsGeoJSON(geometry::geometry)::json AS geometry
        FROM public.official_zones WHERE {} ORDER BY effective_from DESC, id
    """).format(sql.SQL(" AND ").join(predicates))
    if near is not None:
        statement += sql.SQL(" LIMIT 15")
    return db.execute(statement, params).fetchall()


def distance_between_points(db: Connection[DictRow], a: tuple[float, float], b: tuple[float, float]) -> float:
    row = db.execute("""
        SELECT ST_Distance(
            ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
            ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
        ) AS meters
    """, (*a, *b)).fetchone()
    assert row is not None
    return row["meters"]


def incident_feature(incident: PublicIncident) -> dict:
    return {
        "type": "Feature",
        "id": str(incident.id),
        "geometry": incident.location.model_dump(mode="json"),
        "properties": incident.model_dump(mode="json", exclude={"id", "location"}),
    }
