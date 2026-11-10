import logging
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import ApiError
from app.schemas.routes import RouteLine, RouteQuery, parse_pair, separation_km

logger = logging.getLogger(__name__)
demo_lock = Lock()
demo_last_request = float("-inf")


class PrivateLocationLogs(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Both these loggers normally include coordinates in request URLs.
        if record.name == "uvicorn.access" and isinstance(record.args, tuple) and len(record.args) == 5:
            client, method, path, version, status = record.args
            endpoint, separator, _ = str(path).partition("?")
            if separator and endpoint in {"/api/routes", "/api/incidents/nearby"}:
                record.args = (client, method, endpoint, version, status)
        if record.name == "httpx" and "/route/v1/" in record.getMessage():
            return False
        return True


def protect_location_logs() -> None:
    for name in ("uvicorn.access", "httpx"):
        logging.getLogger(name).addFilter(PrivateLocationLogs())


def fetch_routes(query: RouteQuery, settings: Settings) -> list[RouteLine]:
    base = (settings.routing_service_url or "").rstrip("/")
    try:
        url = urlsplit(base)
        if not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError
        if url.scheme != "https" and not (url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost", "::1"}):
            raise ValueError
    except ValueError as exc:
        raise ApiError(503, "routing_unavailable", "Driving routes are unavailable until a routing provider is configured") from exc

    if url.hostname == "routing.openstreetmap.de":
        global demo_last_request
        with demo_lock:
            now = monotonic()
            if now - demo_last_request < 1:
                raise ApiError(429, "routing_rate_limited", "Wait a moment before requesting another route")
            demo_last_request = now

    origin, destination = parse_pair(query.origin), parse_pair(query.destination)
    coordinates = ";".join(f"{lng:.6f},{lat:.6f}" for lng, lat in (origin, destination))
    try:
        response = httpx.get(f"{base}/route/v1/driving/{coordinates}", params={
            "alternatives": query.alternatives - 1 if query.alternatives > 1 else "false",
            "geometries": "geojson", "overview": "full", "steps": "false", "radiuses": "500;500",
        }, headers={"User-Agent": "MehfoozAI-routing/0.2"}, timeout=httpx.Timeout(8, connect=3), follow_redirects=False)
        if response.status_code == 429 or response.status_code >= 500:
            raise httpx.HTTPStatusError("routing provider unavailable", request=response.request, response=response)
        payload = response.json()
    except (httpx.HTTPError, httpx.InvalidURL, ValueError) as exc:
        logger.info("routing provider request failed: %s", type(exc).__name__)
        raise ApiError(503, "routing_unavailable", "The routing provider is temporarily unavailable") from exc

    if isinstance(payload, dict) and payload.get("code") in ("NoRoute", "NoSegment"):
        return []
    if not response.is_success or not isinstance(payload, dict) or payload.get("code") != "Ok" or not isinstance(payload.get("routes"), list):
        raise ApiError(502, "routing_response_invalid", "The routing provider returned an unusable response")
    routes = []
    seen = set()
    for row in payload["routes"][:query.alternatives]:
        if not isinstance(row, dict):
            continue
        try:
            route = RouteLine(geometry=row.get("geometry"), distance_m=row.get("distance"), duration_s=row.get("duration"))
        except ValidationError:
            continue
        shape = tuple(route.geometry.coordinates)
        if separation_km(origin, shape[0]) > .75 or separation_km(destination, shape[-1]) > .75:
            continue
        if shape not in seen:
            seen.add(shape)
            routes.append(route)
    if payload["routes"] and not routes:
        raise ApiError(502, "routing_response_invalid", "The routing provider returned unusable route geometry")
    return routes
