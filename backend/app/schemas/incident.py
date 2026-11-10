from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.schemas.common import Bounds, Latitude, Longitude, Mode, Point, Timestamp

Category = Literal[
    "robbery", "theft", "harassment", "suspicious_activity", "road_accident",
    "unsafe_road", "poor_lighting", "landslide", "road_closure", "other",
]
PublicStatus = Literal["pending", "corroborated", "verified"]
PageLimit = Annotated[int, Field(ge=1, le=100)]


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)

    category: Category
    description: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    latitude: Latitude
    longitude: Longitude
    occurred_at: Timestamp

    @field_validator("description")
    @classmethod
    def reject_null_byte(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("Description contains an invalid character")
        return value

    @field_validator("occurred_at")
    @classmethod
    def check_time(cls, value: datetime) -> datetime:
        if value > datetime.now(UTC):
            raise ValueError("Incident time must be at or before submission")
        return value


class IncidentQuery(Bounds):
    category: Category | None = None
    verification_status: Literal["pending", "corroborated", "verified", "rejected"] | None = None
    start_time: Timestamp | None = None
    end_time: Timestamp | None = None
    limit: PageLimit = 50
    offset: Annotated[int, Field(ge=0, le=10_000)] = 0
    mode: Mode = "live"

    @model_validator(mode="after")
    def validate_window(self) -> "IncidentQuery":
        if self.start_time is not None and self.end_time is not None and self.start_time >= self.end_time:
            raise ValueError("Start time must be before end time")
        return self


class NearbyQuery(BaseModel):
    latitude: Latitude
    longitude: Longitude
    radius_meters: Annotated[float, Field(gt=0, le=5_000)] = 500
    limit: PageLimit = 50
    mode: Mode = "live"


class PublicIncident(BaseModel):
    id: UUID
    category: Category
    public_summary: str | None
    location: Point
    occurred_at: datetime
    created_at: datetime
    severity: int | None
    verification_status: PublicStatus
    source: Literal["community", "demo"]
    is_demo: bool


class NearbyIncident(PublicIncident):
    distance_meters: float


class IncidentPage(BaseModel):
    items: list[PublicIncident]
    limit: int
    offset: int
    mode: Mode


class NearbyResults(BaseModel):
    items: list[NearbyIncident]
    mode: Mode
