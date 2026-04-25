from fastapi import APIRouter, Depends, HTTPException, Request, Response, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt
from typing import Optional

from app.db.session import get_db
from app.core.config import settings
from app.core.auth import hash_password, verify_password, create_access_token, create_refresh_token
from app.schemas.schemas import RegisterRequest, LoginRequest, TokenResponse, RefreshRequest, UserOut
from app.db.crud.user import get_user_by_email, create_user, get_user_by_id
from app.services.email_service import send_welcome_email
from app.core.limiter import limiter
from app.core.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 วัน


def _set_refresh_cookie(response: Response, refresh_token: str):
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=REFRESH_COOKIE_MAX_AGE,
        path="/api/v1/auth/refresh",
    )

@router.post("/register", response_model=TokenResponse)
@limiter.limit("10/minute")
async def register(request: Request, response: Response, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = await create_user(db, {
        "email": body.email,
        "hashed_password": hash_password(body.password),
        "full_name": body.full_name,
        "phone": body.phone,
    })

    await send_welcome_email(user.email, user.full_name)

    refresh_token = create_refresh_token(user.id)
    _set_refresh_cookie(response, refresh_token)

    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, response: Response, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_email(db, body.email)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    refresh_token = create_refresh_token(user.id)
    _set_refresh_cookie(response, refresh_token)

    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("20/minute")
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    cookie_token: Optional[str] = Cookie(None, alias="refresh_token"),
    body: Optional[RefreshRequest] = None,  # รองรับทั้ง cookie และ body (backward compat)
):
    token = cookie_token or (body.refresh_token if body else None)
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = await get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    new_refresh_token = create_refresh_token(user.id)
    _set_refresh_cookie(response, new_refresh_token)

    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=new_refresh_token,
    )


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="refresh_token", path="/api/v1/auth/refresh")
    return {"message": "Logged out"}


@router.get("/me", response_model=UserOut)
async def me(current_user=Depends(get_current_user)):
    return current_user