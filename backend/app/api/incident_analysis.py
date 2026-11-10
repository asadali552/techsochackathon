from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from app.api.dependencies import CurrentUser, Database
from app.core.config import Settings, get_settings
from app.schemas.common import Success
from app.schemas.incident_analysis import IncidentAnalysis
from app.services.incident_analysis import analyze_incident, get_analysis

router = APIRouter(prefix="/ai/incidents", tags=["incident analysis"])
Configuration = Annotated[Settings, Depends(get_settings)]


@router.post("/{incident_id}/analyze")
def analyze(
    incident_id: UUID, user_id: CurrentUser, db: Database, config: Configuration, response: Response,
) -> Success[IncidentAnalysis]:
    result = analyze_incident(db, incident_id, user_id, config)
    response.headers["Cache-Control"] = "no-store"
    if result.status == "processing":
        response.status_code = 202
    return Success[IncidentAnalysis](data=result)


@router.get("/{incident_id}/analysis")
def analysis(
    incident_id: UUID, user_id: CurrentUser, db: Database, config: Configuration, response: Response,
) -> Success[IncidentAnalysis]:
    response.headers["Cache-Control"] = "no-store"
    return Success[IncidentAnalysis](data=get_analysis(db, incident_id, user_id, config))
