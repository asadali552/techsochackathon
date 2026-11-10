from fastapi import APIRouter

from app.api.dependencies import Database
from app.core.errors import ApiError
from app.schemas.health import HealthData, HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(data=HealthData())


@router.get("/ready", response_model=HealthResponse)
def ready(db: Database) -> HealthResponse:
    row = db.execute("""
        SELECT ST_SRID(ST_SetSRID(ST_MakePoint(0, 0), 4326)) = 4326
           AND to_regclass('public.profiles') IS NOT NULL
           AND to_regclass('public.incidents') IS NOT NULL
           AND to_regclass('public.official_zones') IS NOT NULL
           AND to_regclass('public.incident_ai_analysis') IS NOT NULL
           AND to_regclass('public.route_references') IS NOT NULL AS ready
    """).fetchone()
    if not row or not row["ready"]:
        raise ApiError(503, "database_unavailable", "Database schema is not installed")
    return HealthResponse(data=HealthData())
