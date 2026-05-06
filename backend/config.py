import os
from dotenv import load_dotenv

load_dotenv()


def _clean_env(value: str) -> str:
    if not value:
        return ""
    return value.strip().replace('"', "").replace("'", "")


def clean_instagram_username(value: str) -> str:
    """
    Accepts:
    - mrkousikai
    - @mrkousikai
    - https://instagram.com/mrkousikai/
    - www.instagram.com/mrkousikai

    Returns:
    - mrkousikai
    """
    if not value:
        return ""

    username = _clean_env(value).strip()
    username = username.replace("https://", "").replace("http://", "")
    username = username.replace("www.instagram.com/", "")
    username = username.replace("instagram.com/", "")
    username = username.replace("@", "")
    username = username.strip().strip("/")

    if "/" in username:
        username = username.split("/", 1)[0]

    if "?" in username:
        username = username.split("?", 1)[0]

    return username.strip().lower()


VERIFY_TOKEN = _clean_env(os.getenv("VERIFY_TOKEN", ""))
INSTAGRAM_ACCESS_TOKEN = _clean_env(os.getenv("INSTAGRAM_ACCESS_TOKEN", ""))
IG_BUSINESS_ACCOUNT_ID = _clean_env(os.getenv("IG_BUSINESS_ACCOUNT_ID", ""))

# Optional fallback only.
# If empty, backend will auto-fetch username from IG_BUSINESS_ACCOUNT_ID / token.
OWNER_USERNAME = clean_instagram_username(os.getenv("OWNER_USERNAME", ""))
OWNER_IGSID = _clean_env(os.getenv("OWNER_IGSID", ""))

# Optional Instagram OAuth / frontend values, safe to keep if unused.
INSTAGRAM_CLIENT_ID = _clean_env(os.getenv("INSTAGRAM_CLIENT_ID", ""))
INSTAGRAM_CLIENT_SECRET = _clean_env(os.getenv("INSTAGRAM_CLIENT_SECRET", ""))
INSTAGRAM_REDIRECT_URI = _clean_env(os.getenv("INSTAGRAM_REDIRECT_URI", ""))
JWT_SECRET = _clean_env(os.getenv("JWT_SECRET", ""))
FRONTEND_URL = _clean_env(os.getenv("FRONTEND_URL", ""))
