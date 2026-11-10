from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from time import monotonic
from uuid import UUID, uuid4

from app.core.errors import ApiError
from app.schemas.assistant import Place, Plan
from app.schemas.common import Mode

TTL = 15 * 60


@dataclass
class Conversation:
    owner: str
    mode: Mode
    expires: float
    gate: Lock = field(default_factory=Lock)
    area: Place | None = None
    origin: Place | None = None
    destination: Place | None = None
    departure: datetime | None = None
    route_ids: list[UUID] = field(default_factory=list)
    routes_expires: float = 0
    pending: tuple[Plan, str, list[Place], Place | None] | None = None


_lock = Lock()
_sessions: dict[UUID, Conversation] = {}
_rate: dict[str, tuple[float, int]] = {}


def _owned(key: UUID, owner: str, mode: Mode) -> Conversation:
    item = _sessions.get(key)
    if item is None or item.owner != owner or item.mode != mode or item.expires <= monotonic():
        raise ApiError(404, "conversation_expired", "This chat has expired. Clear it to start again.")
    return item


def checkout(key: UUID | None, owner: str, mode: Mode) -> tuple[UUID, Conversation]:
    now = monotonic()
    with _lock:
        for expired in [key for key, item in _sessions.items() if item.expires <= now]:
            del _sessions[expired]
        for expired_owner in [key for key, (end, _) in _rate.items() if end <= now]:
            del _rate[expired_owner]
        end, count = _rate.get(owner, (now + 60, 0))
        if count >= 15 or (owner not in _rate and len(_rate) >= 512):
            raise ApiError(429, "assistant_rate_limited", "Please wait a moment before asking another question.")
        _rate[owner] = end, count + 1
        if key is None:
            if len(_sessions) >= 256:
                raise ApiError(503, "assistant_busy", "The assistant is busy. Try again shortly.")
            key = uuid4()
            _sessions[key] = Conversation(owner, mode, now + TTL)
        item = _owned(key, owner, mode)
        if not item.gate.acquire(blocking=False):
            raise ApiError(409, "conversation_busy", "Wait for the current question to finish.")
        item.expires = now + TTL
        return key, item


def clear(key: UUID, owner: str, mode: Mode) -> None:
    with _lock:
        _owned(key, owner, mode)
        del _sessions[key]
