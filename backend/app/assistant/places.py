import logging
import re
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from app.ai.client import redact
from app.core.config import Settings
from app.core.errors import ApiError
from app.schemas.routes import separation_km
from app.schemas.assistant import Place
from app.schemas.common import Point

# Existing pilot landmarks and named GeoNames locality centers. Hunza is a region.
LANDMARKS = (
    (("multan cantt", "multan cantonment railway station", "cantt station"), "Multan Cantonment Railway Station", 30.1804, 71.4446),
    (("ghanta ghar",), "Ghanta Ghar, Multan", 30.198803, 71.467842),
    (("tomb of shah rukn-e-alam",), "Tomb of Shah Rukn-e-Alam, Multan", 30.199172, 71.471646),
    (("gulgasht colony", "gulgasht"), "Gulgasht Colony, Multan", 30.22739, 71.47412),
    (("multan",), "Multan, Punjab", 30.19679, 71.47824),
    (("lahore",), "Lahore, Punjab", 31.558, 74.35071),
    (("islamabad",), "Islamabad, Pakistan", 33.72148, 73.04329),
    (("skardu",), "Skardu, Gilgit-Baltistan", 35.29787, 75.63372),
    (("naran",), "Naran, Kaghan Valley", 34.9045, 73.647),
    (("karimabad", "hunza"), "Karimabad, Hunza", 36.319, 74.6643),
    (("aliabad", "hunza"), "Aliabad, Hunza", 36.30598, 74.61667),
)
COORDINATES = r"(-?\d{1,3}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)"
_cache: dict[tuple[str, str], tuple[float, list[Place]]] = {}
_lock = Lock()
_last_request = 0.0


def resolve(name: str, config: Settings) -> list[Place]:
    key = " ".join(name.lower().strip(" .?!").split())
    if match := re.fullmatch(COORDINATES, key):
        try:
            lat, lon = map(float, match.groups())
            return [Place(label="Provided coordinates", point=Point(type="Point", coordinates=(lon, lat)), source="coordinates")]
        except ValidationError:
            return []
    matches = [
        Place(label=label, point=Point(type="Point", coordinates=(lon, lat)), source="gazetteer")
        for aliases, label, lat, lon in LANDMARKS if key in aliases or key == label.lower()
    ]
    return matches or geocode(key, config)


def geocode(name: str, config: Settings) -> list[Place]:
    global _last_request
    base = (config.geocoding_service_url or "").rstrip("/")
    try:
        endpoint = urlsplit(base)
        host = (endpoint.hostname or "").lower().rstrip(".")
        valid = endpoint.scheme == "https" or (endpoint.scheme == "http" and host in {"localhost", "127.0.0.1", "::1"})
        if not host or host == "nominatim.openstreetmap.org" or not valid or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
            raise ValueError
    except ValueError:
        raise ApiError(503, "geocoding_unavailable", "Place lookup is unavailable. Enter a known landmark or latitude, longitude.") from None

    # Only public place names go to the optional provider.
    if (redact(name) != name or not re.fullmatch(r"[\w\s.,'’()/-]{2,100}", name)
            or not any(c.isalpha() for c in name) or re.match(r"^\d+\s", name)):
        return []
    cache_key = (base, name)
    with _lock:
        now = monotonic()
        if cache_key in _cache and _cache[cache_key][0] > now:
            return _cache[cache_key][1]
        if now - _last_request < 1:
            raise ApiError(503, "geocoding_busy", "Place lookup is busy. Try again in a moment.")
        _last_request = now
    # httpx's request log contains the place query string.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        response = httpx.get(
            f"{base}/search", params={"q": name, "format": "jsonv2", "countrycodes": "pk", "limit": 5},
            headers={"User-Agent": "MehfoozAI/0.2 (Pakistan travel safety)", "Accept-Language": "en"},
            timeout=min(3, config.assistant_timeout_seconds), follow_redirects=False,
        )
        response.raise_for_status()
        records = response.json()
        if not isinstance(records, list):
            raise ValueError
    except (httpx.HTTPError, httpx.InvalidURL, ValueError):
        raise ApiError(503, "geocoding_unavailable", "Place lookup is temporarily unavailable. Try latitude, longitude.") from None
    matches = []
    for item in records[:5]:
        try:
            if not isinstance(item["display_name"], str) or not item["display_name"].strip():
                continue
            point = Point(type="Point", coordinates=(item["lon"], item["lat"]))
            match = Place(label=item["display_name"][:220], point=point, source="OpenStreetMap")
        except (KeyError, TypeError, ValidationError):
            continue
        if all(separation_km(match.point.coordinates, other.point.coordinates) >= 1 for other in matches):
            matches.append(match)
    with _lock:
        _cache.pop(cache_key, None)
        if len(_cache) >= 128:
            _cache.pop(next(iter(_cache)))
        _cache[cache_key] = (monotonic() + (3600 if matches else 300), matches)
    return matches
