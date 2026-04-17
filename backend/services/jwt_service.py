import jwt
import time
from config import JWT_SECRET


def create_token(data: dict):
    payload = {
        **data,
        "exp": int(time.time()) + (86400 * 7),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_token(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None
