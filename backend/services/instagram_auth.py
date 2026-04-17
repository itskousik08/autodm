import requests
from config import (
    INSTAGRAM_CLIENT_ID,
    INSTAGRAM_CLIENT_SECRET,
    INSTAGRAM_REDIRECT_URI,
)

AUTH_URL = "https://api.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
GRAPH_URL = "https://graph.instagram.com"


def get_instagram_login_url():
    return (
        f"{AUTH_URL}"
        f"?client_id={INSTAGRAM_CLIENT_ID}"
        f"&redirect_uri={INSTAGRAM_REDIRECT_URI}"
        f"&scope=user_profile,user_media"
        f"&response_type=code"
    )


def exchange_code_for_token(code: str):
    payload = {
        "client_id": INSTAGRAM_CLIENT_ID,
        "client_secret": INSTAGRAM_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri": INSTAGRAM_REDIRECT_URI,
        "code": code,
    }

    response = requests.post(TOKEN_URL, data=payload)
    return response.json()


def get_user_profile(access_token: str):
    url = f"{GRAPH_URL}/me"
    params = {
        "fields": "id,username,account_type",
        "access_token": access_token,
    }

    response = requests.get(url, params=params)
    return response.json()
