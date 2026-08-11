"""Authentication endpoints: register, login, logout, me."""
from fastapi import APIRouter, Request, Response, Depends
from app.models.schemas import UserRegister, UserLogin, AuthResponse, UserMe
from app.services.auth import (
    register_user,
    login_user,
    logout_user,
    get_current_user,
    generate_csrf_token,
    set_session_cookie,
    set_csrf_cookie,
    clear_auth_cookies,
    verify_csrf,
)
from app.config import settings

router = APIRouter()


def _require_csrf():
    def _check(request: Request):
        verify_csrf(request)
    return Depends(_check)


@router.post("/auth/register", response_model=AuthResponse, status_code=201)
async def register(request: Request, data: UserRegister):
    user = register_user(data)
    return AuthResponse(user_id=user["user_id"], username=user["username"])


@router.post("/auth/login", response_model=AuthResponse, status_code=200)
async def login(request: Request, response: Response, data: UserLogin):
    token, user = login_user(data, request)
    csrf_token = generate_csrf_token()
    set_session_cookie(response, token)
    set_csrf_cookie(response, csrf_token)
    return AuthResponse(user_id=user["user_id"], username=user["username"])


@router.post("/auth/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    _csrf=_require_csrf(),
):
    token = request.cookies.get(settings.auth_cookie_name)
    if token:
        logout_user(token)
    clear_auth_cookies(response)
    return Response(status_code=204)


@router.get("/auth/me", response_model=UserMe)
async def me(user: dict = Depends(get_current_user)):
    return UserMe(user_id=user["user_id"], username=user["username"])
