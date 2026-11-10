from threading import BoundedSemaphore
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials

from app.assistant.agent import assist
from app.assistant.session import checkout, clear
from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.core.security import bearer_scheme, verify_user
from app.schemas.assistant import ChatRequest, ChatResult, ChatSession
from app.schemas.common import Success

router = APIRouter(prefix="/ai/chat", tags=["travel assistant"])
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]
Config = Annotated[Settings, Depends(get_settings)]
_capacity = BoundedSemaphore(8)


def owner(body: ChatSession, request: Request, credentials: Credentials, config: Config) -> str:
    if body.mode == "demo" and credentials is None:
        return f"demo:{request.client.host if request.client else 'unknown'}"
    return str(verify_user(credentials, config))


@router.post("")
def chat(body: ChatRequest, request: Request, response: Response, credentials: Credentials, config: Config) -> Success[ChatResult]:
    if not _capacity.acquire(blocking=False):
        raise ApiError(503, "assistant_busy", "The assistant is busy. Try again shortly.")
    try:
        identity = owner(body, request, credentials, config)
        key, session = checkout(body.conversation_id, identity, body.mode)
        try:
            use_model = credentials is not None or bool(config.assistant_gemini_in_demo and config.gemini_api_key)
            result = assist(key, session, body, config, use_model=use_model)
        finally:
            session.gate.release()
    finally:
        _capacity.release()
    response.headers["Cache-Control"] = "no-store"
    return Success[ChatResult](data=result)


@router.post("/clear")
def clear_chat(body: ChatSession, request: Request, response: Response, credentials: Credentials, config: Config) -> Success[dict[str, bool]]:
    identity = owner(body, request, credentials, config)
    if body.conversation_id:
        clear(body.conversation_id, identity, body.mode)
    response.headers["Cache-Control"] = "no-store"
    return Success[dict[str, bool]](data={"cleared": True})
