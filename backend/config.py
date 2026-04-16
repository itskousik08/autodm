import os
from dotenv import load_dotenv

load_dotenv()


def _clean_env(value: str) -> str:
    if not value:
        return ""
    return value.strip().replace('"', "").replace("'", "")


VERIFY_TOKEN = _clean_env(os.getenv("VERIFY_TOKEN", ""))
INSTAGRAM_ACCESS_TOKEN = _clean_env(os.getenv("INSTAGRAM_ACCESS_TOKEN", ""))
IG_BUSINESS_ACCOUNT_ID = _clean_env(os.getenv("IG_BUSINESS_ACCOUNT_ID", ""))
