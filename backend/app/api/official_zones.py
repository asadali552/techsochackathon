from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import Database
from app.schemas.common import Success
from app.schemas.official_zone import ZoneCollection, ZoneFeature, ZoneProperties, ZoneQuery
from app.services.geospatial_service import find_official_zones

router = APIRouter(tags=["official zones"])


@router.get("/official-zones")
def official_zones(query: Annotated[ZoneQuery, Query()], db: Database) -> Success[ZoneCollection]:
    features = [
        ZoneFeature(id=row["id"], geometry=row["geometry"], properties=ZoneProperties.model_validate(row))
        for row in find_official_zones(db, query)
    ]
    return Success[ZoneCollection](data=ZoneCollection(features=features, mode=query.mode))
