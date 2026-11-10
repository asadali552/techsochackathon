from typing import Annotated
from uuid import UUID

import httpx
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ValidationError

from app.core.config import Settings, get_settings
from app.core.errors import ApiError

bearer_scheme = HTTPBearer(auto_error=False)


class AuthUser(BaseModel):
    id: UUID
    is_anonymous: bool = False


def verify_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    config: Annotated[Settings, Depends(get_settings)],
) -> UUID:
    if credentials is None:
        raise ApiError(401, "unauthorized", "A Supabase bearer token is required")
    if not config.supabase_url or not config.supabase_anon_key:
        raise ApiError(503, "auth_unavailable", "Supabase Auth is not configured")

    try:
        response = httpx.get(
            f"{config.supabase_url.rstrip('/')}/auth/v1/user",
            headers={"apikey": config.supabase_anon_key, "Authorization": f"Bearer {credentials.credentials}"},
            timeout=5,
        )
    except httpx.RequestError as exc:
        raise ApiError(503, "auth_unavailable", "Supabase Auth is temporarily unavailable") from exc

    if response.status_code in (400, 401, 403):
        raise ApiError(401, "unauthorized", "Invalid Supabase session")
    if response.status_code != 200:
        raise ApiError(503, "auth_unavailable", "Supabase Auth is temporarily unavailable")

    try:
        user = AuthUser.model_validate_json(response.content)
    except ValidationError as exc:
        raise ApiError(503, "auth_unavailable", "Invalid response from Supabase Auth") from exc
    if user.is_anonymous:
        raise ApiError(403, "forbidden", "Sign in with a registered account to submit reports")
    return user.id
