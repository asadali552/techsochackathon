from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.dependencies import Database
from app.core.config import Settings, get_settings
from app.routing.comparison import compare_routes, route_options
from app.schemas.common import Success
from app.schemas.routes import RouteComparison, RouteComparisonRequest, RouteList, RouteQuery

router = APIRouter(prefix="/routes", tags=["routes"])
Configuration = Annotated[Settings, Depends(get_settings)]


@router.get("")
def routes(query: Annotated[RouteQuery, Query()], db: Database, config: Configuration, response: Response) -> Success[RouteList]:
    response.headers["Cache-Control"] = "no-store"
    return Success[RouteList](data=route_options(db, query, config))


@router.post("/compare")
def compare(query: RouteComparisonRequest, db: Database, config: Configuration, response: Response) -> Success[RouteComparison]:
    response.headers["Cache-Control"] = "no-store"
    return Success[RouteComparison](data=compare_routes(db, query, config))
