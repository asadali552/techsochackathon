from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from psycopg import Connection, sql
from psycopg.rows import DictRow

from app.core.config import Settings
from app.core.errors import ApiError
from app.schemas.heatmap import (
    CellEvidence, CellProperties, HeatmapCell, HeatmapCells, HeatmapQuery, HeatmapResult,
    HeatmapWindow, Methodology, Period,
)
from app.services.geospatial_service import ENVELOPE, POINT, PUBLIC_REPORTS, bounds_params

SCORING_VERSION = "reported-risk-v1"
CELL_SIZES = (500, 750, 1000, 1500, 2500)
MAX_CELLS = 500
HALF_LIFE_DAYS = 14
HOURS: dict[Period, tuple[int, int]] = {
    "full_day": (0, 24), "morning": (6, 12), "afternoon": (12, 17),
    "evening": (17, 22), "night": (22, 6),
}
WORLD_BOX = sql.SQL("""ST_MakeBox2D(
    ST_MakePoint(-20037508.342789, -20037508.342789),
    ST_MakePoint(20037508.342789, 20037508.342789)
)""")
ROAD_CATEGORIES = {"road_accident", "unsafe_road", "poor_lighting", "landslide", "road_closure"}

WEIGHT = sql.SQL("""ROUND((
    severity * CASE verification_status WHEN 'verified' THEN 1.0 ELSE 0.75 END
    * POWER(2.0, -GREATEST(0, EXTRACT(epoch FROM (%(anchor)s - occurred_at))) / (%(half_life)s * 86400.0))
    * GREATEST(0.25, 1.0 - 0.75 * {distance} / {radius})
    * CASE category
        WHEN 'robbery' THEN 1.25 WHEN 'road_accident' THEN 1.2
        WHEN 'suspicious_activity' THEN 0.7 WHEN 'other' THEN 0.8 ELSE 1.0 END
)::numeric, 6)""")
PERIOD_FILTER = sql.SQL("""CASE WHEN %(first_hour)s < %(last_hour)s
    THEN hour >= %(first_hour)s AND hour < %(last_hour)s
    ELSE hour >= %(first_hour)s OR hour < %(last_hour)s END""")

# Select a bounded grid before generating polygons. Index prefiltering uses the full
# selected cells so moving the viewport within a cell does not change its score.
GRID_QUERY = sql.SQL("""
    WITH viewport AS (
        SELECT ST_Transform({envelope}, 3857) AS geom
    ), chosen AS (
        SELECT size, geom FROM viewport CROSS JOIN unnest(%(sizes)s::int[]) AS size
        WHERE (floor(ST_XMax(geom) / size) - floor(ST_XMin(geom) / size) + 1)
            * (floor(ST_YMax(geom) / size) - floor(ST_YMin(geom) / size) + 1) <= %(max_cells)s
        ORDER BY size LIMIT 1
    ), grid AS (
        SELECT square.*, size FROM chosen
        CROSS JOIN LATERAL ST_SquareGrid(size, chosen.geom) AS square
    ), scope AS (
        SELECT ST_Transform(ST_ClipByBox2D(ST_SetSRID(ST_Extent(geom)::geometry, 3857), {world}), 4326) AS geom FROM grid
    ), public_evidence AS (
        SELECT category, verification_status, COALESCE(severity, 1) AS severity, occurred_at,
               ST_Transform(public_location::geometry, 3857) AS point,
               EXTRACT(hour FROM occurred_at AT TIME ZONE %(timezone)s) AS hour
        FROM public.incidents CROSS JOIN scope
        WHERE {visible} AND verification_status IN ('corroborated', 'verified')
          AND occurred_at >= %(start)s AND occurred_at < %(end)s
          AND public_location::geometry && scope.geom
    ), eligible AS (
        SELECT * FROM public_evidence
        WHERE {period_filter}
    ), category_totals AS (
        SELECT grid.i, grid.j, category, COUNT(*) AS report_count, MAX(occurred_at) AS latest,
               SUM({weight}) AS weight
        FROM eligible CROSS JOIN chosen
        JOIN grid ON grid.i = floor(ST_X(point) / chosen.size)
                 AND grid.j = floor(ST_Y(point) / chosen.size)
        GROUP BY grid.i, grid.j, category
    ), aggregated AS (
        SELECT i, j, jsonb_object_agg(category, jsonb_build_object(
            'count', report_count, 'latest', latest, 'weight', weight::text
        )) AS categories
        FROM category_totals GROUP BY i, j
    )
    SELECT grid.i, grid.j, grid.size, COALESCE(categories, '{{}}'::jsonb) AS categories,
           ST_AsGeoJSON(ST_Transform(ST_ClipByBox2D(grid.geom, {world}), 4326))::json AS geometry
    FROM grid LEFT JOIN aggregated USING (i, j)
    ORDER BY grid.i, grid.j
""").format(
    envelope=ENVELOPE, visible=PUBLIC_REPORTS, world=WORLD_BOX, period_filter=PERIOD_FILTER,
    weight=WEIGHT.format(distance=sql.SQL("ST_Distance(point, ST_Centroid(grid.geom))"), radius=sql.SQL("(grid.size / SQRT(2.0))")),
)

RADIUS_QUERY = sql.SQL("""
    WITH local_reports AS (
        SELECT category, verification_status, coalesce(severity, 1) AS severity, occurred_at,
               ST_Distance(public_location, {point}) AS distance,
               extract(hour FROM occurred_at AT TIME ZONE %(timezone)s) AS hour
        FROM public.incidents
        WHERE {visible} AND verification_status IN ('corroborated', 'verified')
          AND occurred_at >= %(start)s AND occurred_at < %(end)s
          AND ST_DWithin(public_location, {point}, %(radius_meters)s)
    )
    SELECT category, count(*) AS count, max(occurred_at) AS latest, sum({weight}) AS weight
    FROM local_reports WHERE {period_filter} GROUP BY category
""").format(
    point=POINT, visible=PUBLIC_REPORTS, period_filter=PERIOD_FILTER,
    weight=WEIGHT.format(distance=sql.SQL("distance"), radius=sql.SQL("%(radius_meters)s")),
)


def radius_evidence(db: Connection[DictRow], *, latitude: float, longitude: float, radius: int,
                    is_demo: bool, period: Period, start: datetime, end: datetime,
                    now: datetime, config: Settings) -> tuple[CellEvidence, CellEvidence]:
    first, last = HOURS[period]
    rows = db.execute(RADIUS_QUERY, {
        "latitude": latitude, "longitude": longitude, "radius_meters": radius,
        "is_demo": is_demo, "start": start, "end": end, "anchor": min(now, end),
        "timezone": config.heatmap_timezone, "first_hour": first, "last_hour": last, "half_life": HALF_LIFE_DAYS,
    }).fetchall()
    categories = {
        row["category"]: {"count": row["count"], "latest": row["latest"].isoformat(), "weight": str(row["weight"])}
        for row in rows
    }
    return (
        summarize({key: value for key, value in categories.items() if key not in ROAD_CATEGORIES}, config),
        summarize({key: value for key, value in categories.items() if key in ROAD_CATEGORIES}, config),
    )


def summarize(categories: dict, config: Settings) -> CellEvidence:
    counts = {category: totals["count"] for category, totals in categories.items()}
    report_count = sum(counts.values())
    latest = max((datetime.fromisoformat(row["latest"]) for row in categories.values()), default=None)
    if report_count < config.heatmap_min_reports:
        return CellEvidence(
            band="grey", score=None, report_count=report_count, category_counts=counts,
            latest_report_at=latest, coverage="limited" if report_count else "unavailable",
        )
    weight = sum(Decimal(row["weight"]) for row in categories.values())
    score = min(100, int((weight * 20).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
    band = "red" if score >= config.heatmap_elevated_threshold else (
        "yellow" if score >= config.heatmap_moderate_threshold else "green"
    )
    return CellEvidence(
        band=band, score=score, report_count=report_count,
        category_counts=counts, latest_report_at=latest, coverage="sufficient",
    )


def heatmap(db: Connection[DictRow], query: HeatmapQuery, config: Settings, now: datetime | None = None) -> HeatmapResult:
    generated_at = now or datetime.now(UTC)
    end = query.end_time or generated_at
    try:
        start = query.start_time or end - timedelta(days=30)
    except OverflowError as exc:
        raise ApiError(422, "validation_error", "Choose a later end date or provide a start date") from exc
    if not timedelta(0) < end - start <= timedelta(days=90):
        raise ApiError(422, "validation_error", "Choose a date range between 0 and 90 days")
    first_hour, last_hour = HOURS[query.period] if query.local_hour is None else (query.local_hour, query.local_hour + 1)
    sizes = [query.cell_size] if query.cell_size is not None else [
        size for size in CELL_SIZES if size >= config.heatmap_cell_size
    ]
    is_demo = query.mode == "demo"
    rows = db.execute(GRID_QUERY, {
        **bounds_params(query), "sizes": sizes, "max_cells": MAX_CELLS,
        "is_demo": is_demo, "start": start, "end": end, "anchor": min(generated_at, end),
        "timezone": config.heatmap_timezone, "first_hour": first_hour,
        "last_hour": last_hour, "half_life": HALF_LIFE_DAYS,
    }).fetchall()
    if not rows or len(rows) > MAX_CELLS:
        raise ApiError(422, "viewport_too_large", "Zoom in to load the heatmap or select a larger cell size")

    cells = []
    for row in rows:
        security = {key: value for key, value in row["categories"].items() if key not in ROAD_CATEGORIES}
        roads = {key: value for key, value in row["categories"].items() if key in ROAD_CATEGORIES}
        cells.append(HeatmapCell(
            id=f'{row["size"]}:{row["i"]}:{row["j"]}', geometry=row["geometry"],
            properties=CellProperties(
                security=summarize(security, config), road_hazards=summarize(roads, config),
                is_demo=is_demo, scoring_version=SCORING_VERSION,
            ),
        ))
    return HeatmapResult(
        cells=HeatmapCells(features=cells), window=HeatmapWindow(start=start, end=end),
        period=query.period, local_hour=query.local_hour, timezone=config.heatmap_timezone,
        generated_at=generated_at, cell_size=rows[0]["size"], mode=query.mode, scoring_version=SCORING_VERSION,
        methodology=Methodology(
            minimum_reports=config.heatmap_min_reports, moderate_threshold=config.heatmap_moderate_threshold,
            elevated_threshold=config.heatmap_elevated_threshold, half_life_days=HALF_LIFE_DAYS,
        ),
    )
