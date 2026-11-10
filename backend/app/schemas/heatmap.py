from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import Bounds, Mode, Timestamp
from app.schemas.incident import Category

CellSize = Literal[500, 750, 1000, 1500, 2500]
Period = Literal["full_day", "morning", "afternoon", "evening", "night"]
Band = Literal["green", "yellow", "red", "grey"]


class HeatmapQuery(Bounds):
    bbox: str | None = Field(default=None, max_length=100)
    period: Period = "full_day"
    local_hour: int | None = Field(default=None, ge=0, le=23)
    start_time: Timestamp | None = Field(default=None, alias="from")
    end_time: Timestamp | None = Field(default=None, alias="to")
    cell_size: CellSize | None = None
    mode: Mode = "live"

    @model_validator(mode="before")
    @classmethod
    def parse_grid_size(cls, values: object) -> object:
        # Query-string values are strings. Literal matching expects the integer form.
        if isinstance(values, dict) and isinstance(values.get("cell_size"), str):
            if values["cell_size"] in {"500", "750", "1000", "1500", "2500"}:
                return {**values, "cell_size": int(values["cell_size"])}
        return values

    @model_validator(mode="after")
    def validate_heatmap(self) -> "HeatmapQuery":
        if self.bbox is not None:
            if self.min_lat is not None:
                raise ValueError("Provide bbox or the four named bounds, not both")
            coordinates = self.bbox.split(",")
            if len(coordinates) != 4:
                raise ValueError("bbox must contain west,south,east,north")
            west, south, east, north = coordinates
            bounds = Bounds(min_lat=south, max_lat=north, min_lng=west, max_lng=east)
            self.min_lat, self.max_lat = bounds.min_lat, bounds.max_lat
            self.min_lng, self.max_lng = bounds.min_lng, bounds.max_lng
        if self.min_lat is None:
            raise ValueError("A bounding box is required")
        if self.min_lat < -85.05112 or self.max_lat > 85.05112:
            raise ValueError("Latitude must be within Web Mercator bounds")
        if self.local_hour is not None and self.period != "full_day":
            raise ValueError("Choose a recurring period or local_hour")
        return self


class CellEvidence(BaseModel):
    band: Band
    score: int | None
    report_count: int
    category_counts: dict[Category, int]
    latest_report_at: datetime | None
    coverage: Literal["sufficient", "limited", "unavailable"]


class CellProperties(BaseModel):
    security: CellEvidence
    road_hazards: CellEvidence
    is_demo: bool
    scoring_version: str


class CellPolygon(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[tuple[float, float]]]


class HeatmapCell(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: CellPolygon
    properties: CellProperties


class HeatmapCells(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[HeatmapCell]


class HeatmapWindow(BaseModel):
    start: datetime = Field(serialization_alias="from")
    end: datetime = Field(serialization_alias="to")


class Methodology(BaseModel):
    minimum_reports: int
    moderate_threshold: int
    elevated_threshold: int
    half_life_days: int


class HeatmapResult(BaseModel):
    cells: HeatmapCells
    window: HeatmapWindow
    period: Period
    local_hour: int | None
    timezone: str
    generated_at: datetime
    cell_size: CellSize
    mode: Mode
    scoring_version: str
    methodology: Methodology
