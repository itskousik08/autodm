from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

from services.instagram_auth import (
    get_instagram_login_url,
    exchange_code_for_token,
    get_user_profile,
)

from services.jwt_service import create_token
from database import get_user_by_instagram_id, save_user
from config import FRONTEND_URL

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/instagram/login")
def instagram_login():
    return RedirectResponse(get_instagram_login_url())


@router.get("/instagram/callback")
def instagram_callback(code: str = Query(...)):
    token_data = exchange_code_for_token(code)

    access_token = token_data.get("access_token")
    if not access_token:
        return {"error": "Token failed"}

    profile = get_user_profile(access_token)

    ig_id = profile.get("id")
    username = profile.get("username")

    if not ig_id:
        return {"error": "Profile fetch failed"}

    user = get_user_by_instagram_id(ig_id)

    if not user:
        user = save_user({
            "instagram_id": ig_id,
            "username": username,
            "access_token": access_token,
        })

    jwt_token = create_token({
        "user_id": ig_id,
        "username": username,
    })

    return RedirectResponse(f"{FRONTEND_URL}/auth-success?token={jwt_token}")
