from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, BeforeValidator, Field, model_validator

Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
Mode = Literal["live", "demo"]


def parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or "T" not in value.upper():
        raise ValueError("Use an ISO 8601 timestamp with a timezone")
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC)
    except (ValueError, OverflowError):
        pass
    raise ValueError("Use an ISO 8601 timestamp with a timezone")


Timestamp = Annotated[AwareDatetime, BeforeValidator(parse_timestamp)]


class Success[T](BaseModel):
    data: T
    error: None = None


class Bounds(BaseModel):
    min_lat: Latitude | None = None
    max_lat: Latitude | None = None
    min_lng: Longitude | None = None
    max_lng: Longitude | None = None

    @model_validator(mode="after")
    def validate_bounds(self) -> "Bounds":
        values = (self.min_lat, self.max_lat, self.min_lng, self.max_lng)
        if all(value is None for value in values):
            return self
        if any(value is None for value in values):
            raise ValueError("Provide all four bounding box coordinates")
        if self.min_lat >= self.max_lat or self.min_lng >= self.max_lng:
            raise ValueError("Each bounding box minimum must be less than its maximum")
        return self


class Point(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: tuple[Longitude, Latitude]
