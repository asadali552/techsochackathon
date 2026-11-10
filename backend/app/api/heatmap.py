from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import Database
from app.core.config import Settings, get_settings
from app.schemas.common import Success
from app.schemas.heatmap import HeatmapQuery, HeatmapResult
from app.services.heatmap_service import heatmap

router = APIRouter(tags=["heatmap"])


@router.get("/heatmap")
def get_heatmap(
    query: Annotated[HeatmapQuery, Query()],
    db: Database,
    config: Annotated[Settings, Depends(get_settings)],
) -> Success[HeatmapResult]:
    return Success[HeatmapResult](data=heatmap(db, query, config))
