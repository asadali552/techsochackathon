from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentUser, Database
from app.core.errors import ApiError
from app.schemas.common import Mode, Success
from app.schemas.incident import (
    IncidentCreate,
    IncidentPage,
    IncidentQuery,
    NearbyIncident,
    NearbyQuery,
    NearbyResults,
    PublicIncident,
)
from app.services.geospatial_service import find_incidents_in_bounds, find_nearby_incidents
from app.services.incident_service import create_incident, get_public_incident

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.post("", status_code=201)
def submit_incident(report: IncidentCreate, user_id: CurrentUser, db: Database) -> Success[PublicIncident]:
    return Success[PublicIncident](data=PublicIncident.model_validate(create_incident(db, user_id, report)))


@router.get("")
def list_incidents(query: Annotated[IncidentQuery, Query()], db: Database) -> Success[IncidentPage]:
    items = [PublicIncident.model_validate(row) for row in find_incidents_in_bounds(db, query)]
    return Success[IncidentPage](data=IncidentPage(items=items, limit=query.limit, offset=query.offset, mode=query.mode))


@router.get("/nearby")
def nearby_incidents(query: Annotated[NearbyQuery, Query()], db: Database) -> Success[NearbyResults]:
    items = [NearbyIncident.model_validate(row) for row in find_nearby_incidents(db, query)]
    return Success[NearbyResults](data=NearbyResults(items=items, mode=query.mode))


@router.get("/{incident_id}")
def incident_detail(incident_id: UUID, db: Database, mode: Mode = "live") -> Success[PublicIncident]:
    row = get_public_incident(db, incident_id, mode)
    if row is None:
        raise ApiError(404, "not_found", "Incident not found")
    return Success[PublicIncident](data=PublicIncident.model_validate(row))
