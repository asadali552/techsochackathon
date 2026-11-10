from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.common import Mode, Point, Timestamp
from app.schemas.heatmap import CellEvidence, HeatmapCell, HeatmapWindow, Methodology, Period
from app.schemas.incident import Category, NearbyIncident
from app.schemas.official_zone import ZoneFeature
from app.schemas.routes import Preference, RouteComparison, RouteList

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Radius = Annotated[int, Field(ge=100, le=5000)]


class ChatSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: UUID | None = None
    mode: Mode = "live"


class ChatRequest(ChatSession):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    location: Point | None = None
    period: Period | None = None
    start_time: Timestamp | None = None
    end_time: Timestamp | None = None
    cell_size: Literal[500, 750, 1000, 1500, 2500] | None = None
    route_ids: list[UUID] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def distinct_routes(self) -> "ChatRequest":
        if len(set(self.route_ids)) != len(self.route_ids):
            raise ValueError("Route IDs must be distinct")
        return self


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["area", "incidents", "advisories", "heatmap", "journey", "compare", "clarify"]
    place: Text | None = None
    origin: Text | None = None
    destination: Text | None = None
    period: Period | None = None
    radius_meters: Radius = 1500
    category: Category | None = None
    preference: Preference = "balanced"
    day_offset: Annotated[int, Field(ge=0, le=7)] | None = None
    departure_hour: Annotated[int, Field(ge=0, le=23)] | None = None
    recent_days: Annotated[int, Field(ge=1, le=90)] = 30


class Place(BaseModel):
    label: str
    point: Point
    source: Literal["gazetteer", "OpenStreetMap", "shared location", "coordinates"]


class AreaEvidence(BaseModel):
    cell: HeatmapCell | None = None
    radius_meters: int | None = None
    security: CellEvidence
    road_hazards: CellEvidence
    window: HeatmapWindow
    methodology: Methodology
    generated_at: datetime
    period: Period
    timezone: str
    cell_size: int | None = None


class EvidenceReference(BaseModel):
    kind: Literal["incident", "official_zone", "route", "area"]
    reference: str
    label: str
    source_url: str | None = None
    as_of: datetime | None = None


class ChatResult(BaseModel):
    conversation_id: UUID
    mode: Mode
    interpretation: Literal["model", "guided"]
    answer: str
    evidence: list[EvidenceReference] = Field(default_factory=list)
    unavailable_sources: list[str] = Field(default_factory=list)
    places: list[Place] = Field(default_factory=list)
    choices: list[Place] = Field(default_factory=list)
    area: AreaEvidence | None = None
    incidents: list[NearbyIncident] = Field(default_factory=list)
    incident_window: HeatmapWindow | None = None
    advisories: list[ZoneFeature] = Field(default_factory=list)
    route_options: RouteList | None = None
    comparison: RouteComparison | None = None
