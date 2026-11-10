from typing import Literal

from pydantic import BaseModel

from app.schemas.common import Success


class HealthData(BaseModel):
    status: Literal["ok"] = "ok"


HealthResponse = Success[HealthData]
