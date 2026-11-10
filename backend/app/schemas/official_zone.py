from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import Bounds, Longitude, Latitude, Mode, Timestamp


class ZoneQuery(Bounds):
    active_only: bool = True
    at: Timestamp | None = None
    mode: Mode = "live"


class ZoneGeometry(BaseModel):
    type: Literal["MultiPolygon"]
    coordinates: list[list[list[tuple[Longitude, Latitude]]]]


class ZoneProperties(BaseModel):
    name: str
    description: str
    designation: Literal["restricted", "unsafe_advisory", "caution", "road_closure"]
    issuing_authority: str
    source_url: str | None
    source_reference: str | None
    effective_from: datetime
    effective_until: datetime | None
    last_verified_at: datetime
    is_demo: bool


class ZoneFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: UUID
    geometry: ZoneGeometry
    properties: ZoneProperties


class ZoneCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[ZoneFeature]
    mode: Mode
