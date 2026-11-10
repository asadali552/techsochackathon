from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.assistant import router as assistant_router
from app.api.health import router as health_router
from app.api.heatmap import router as heatmap_router
from app.api.incident_analysis import router as analysis_router
from app.api.incidents import router as incidents_router
from app.api.official_zones import router as zones_router
from app.api.routes import router as routes_router
from app.core.config import settings
from app.core.errors import install_error_handlers
from app.routing.provider import protect_location_logs

app = FastAPI(title="MehfoozAI", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
install_error_handlers(app)
protect_location_logs()
app.include_router(health_router, prefix="/api")
app.include_router(incidents_router, prefix="/api")
app.include_router(zones_router, prefix="/api")
app.include_router(heatmap_router, prefix="/api")
app.include_router(analysis_router, prefix="/api")
app.include_router(routes_router, prefix="/api")
app.include_router(assistant_router, prefix="/api")
