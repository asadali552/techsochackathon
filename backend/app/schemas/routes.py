from datetime import UTC, datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from app.schemas.common import Latitude, Longitude, Mode, Timestamp
from app.schemas.heatmap import CellEvidence
from app.schemas.official_zone import ZoneFeature

Coordinate = tuple[Longitude, Latitude]
coordinate_adapter = TypeAdapter(Coordinate)
Preference = Literal["balanced", "shortest", "fastest", "fewer_reported_incidents"]


def parse_pair(value: str) -> Coordinate:
    if not isinstance(value, str) or len(value) > 80:
        raise ValueError("Use longitude,latitude")
    return coordinate_adapter.validate_python(value.split(","))


def separation_km(origin: Coordinate, destination: Coordinate) -> float:
    a, b = (tuple(map(radians, pair)) for pair in (origin, destination))
    h = sin((b[1] - a[1]) / 2) ** 2 + cos(a[1]) * cos(b[1]) * sin((b[0] - a[0]) / 2) ** 2
    return 12_742 * asin(sqrt(min(1, h)))


class RouteQuery(BaseModel):
    origin: str = Field(max_length=80)
    destination: str = Field(max_length=80)
    departure_at: Timestamp | None = None
    alternatives: int = Field(default=3, ge=1, le=3)

    @model_validator(mode="after")
    def validate_trip(self) -> "RouteQuery":
        if not .025 <= separation_km(parse_pair(self.origin), parse_pair(self.destination)) <= 500:
            raise ValueError("Choose endpoints at least 25 metres and at most 500 kilometres apart")
        if self.departure_at and abs(self.departure_at - datetime.now(UTC)) > timedelta(days=90):
            raise ValueError("Departure must be within 90 days of today")
        return self


class RouteGeometry(BaseModel):
    type: Literal["LineString"]
    coordinates: list[Coordinate] = Field(min_length=2, max_length=25_000)

    @model_validator(mode="after")
    def nondegenerate(self) -> "RouteGeometry":
        first = self.coordinates[0]
        if all(pair == first for pair in self.coordinates):
            raise ValueError("Route geometry needs distinct coordinates")
        return self


class RouteLine(BaseModel):
    geometry: RouteGeometry
    distance_m: float = Field(gt=0, le=1_000_000)
    duration_s: float = Field(gt=0, le=172_800)


class Route(RouteLine):
    id: UUID


class RouteList(BaseModel):
    routes: list[Route]
    departure_at: datetime
    provider: str


class RouteComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    route_ids: list[UUID] = Field(min_length=1, max_length=3)
    preference: Preference = "balanced"
    mode: Mode = "live"

    @model_validator(mode="after")
    def distinct(self) -> "RouteComparisonRequest":
        if len(self.route_ids) != len(set(self.route_ids)):
            raise ValueError("Route IDs must be distinct")
        return self


class ComparedRoute(Route):
    security: CellEvidence
    road_hazards: CellEvidence
    official_zones: list[ZoneFeature]
    official_coverage: Literal["available", "unavailable"]
    trade_offs: list[str]


class RouteComparison(BaseModel):
    routes: list[ComparedRoute]
    preference: Preference
    mode: Mode
    scoring_version: str
    corridor_m: int
    evidence_window_days: int
    departure_at: datetime
