from __future__ import annotations

from fastapi import APIRouter, Cookie, Response, status

from app.api.deps import ClientDep, CurrentUser, SessionDep, SettingsDep, rate_limit
from app.core.config import Settings
from app.core.errors import AuthError
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut, UserUpdate
from app.services.auth.service import AuthService, IssuedTokens

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "akshara_refresh"
COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, tokens: IssuedTokens, settings: Settings) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        max_age=settings.refresh_token_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=COOKIE_PATH,
    )


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[rate_limit("register")],
)
async def register(
    body: RegisterRequest, session: SessionDep, settings: SettingsDep, client: ClientDep
) -> UserOut:
    user = await AuthService(session, settings).register(
        body.email, body.password, body.display_name, client
    )
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenResponse, dependencies=[rate_limit("login")])
async def login(
    body: LoginRequest,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    client: ClientDep,
) -> TokenResponse:
    tokens = await AuthService(session, settings).login(body.email, body.password, client)
    _set_refresh_cookie(response, tokens, settings)
    return TokenResponse(access_token=tokens.access_token, expires_in=tokens.expires_in)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    client: ClientDep,
    akshara_refresh: str | None = Cookie(default=None),
) -> TokenResponse:
    if not akshara_refresh:
        raise AuthError("Sign in to continue.", code="NO_SESSION")
    try:
        tokens = await AuthService(session, settings).refresh(akshara_refresh, client)
    except AuthError:
        response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
        raise
    _set_refresh_cookie(response, tokens, settings)
    return TokenResponse(access_token=tokens.access_token, expires_in=tokens.expires_in)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    akshara_refresh: str | None = Cookie(default=None),
) -> Response:
    await AuthService(session, settings).logout(akshara_refresh)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH)
    return response


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: UserUpdate, user: CurrentUser, session: SessionDep, settings: SettingsDep
) -> UserOut:
    updated = await AuthService(session, settings).update_profile(
        user,
        display_name=body.display_name,
        preferred_unit=body.preferred_unit,
        allow_external_llm=body.allow_external_llm,
        fields_set=body.model_fields_set,
    )
    return UserOut.model_validate(updated)
