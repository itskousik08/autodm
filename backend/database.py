import json
import os
import threading
from typing import Dict, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "users.json")

# Thread lock to prevent file corruption
_db_lock = threading.Lock()


def _ensure_db_exists():
    """Ensure database file exists"""
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2)


def _load() -> Dict[str, Any]:
    """Load database safely"""
    _ensure_db_exists()

    try:
        with _db_lock:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

                if not isinstance(data, dict):
                    return {}

                return data

    except json.JSONDecodeError:
        print("⚠️ DB corrupted, resetting...")
        return {}
    except Exception as e:
        print("❌ DB LOAD ERROR:", str(e))
        return {}


def _save(data: Dict[str, Any]):
    """Save database safely"""
    try:
        with _db_lock:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("❌ DB SAVE ERROR:", str(e))


# =========================
# USER OPERATIONS
# =========================

def get_user_by_instagram_id(ig_id: str):
    if not ig_id:
        return None

    data = _load()
    return data.get(ig_id)


def save_user(user: Dict[str, Any]):
    if not isinstance(user, dict):
        return None

    ig_id = user.get("instagram_id")
    if not ig_id:
        print("❌ Missing instagram_id")
        return None

    data = _load()

    # Update existing OR create new
    data[ig_id] = {
        "instagram_id": ig_id,
        "username": user.get("username", ""),
        "access_token": user.get("access_token", ""),
    }

    _save(data)
    return data[ig_id]


def update_user_token(ig_id: str, new_token: str):
    data = _load()

    if ig_id not in data:
        return None

    data[ig_id]["access_token"] = new_token
    _save(data)

    return data[ig_id]


def get_all_users():
    return _load()


def delete_user(ig_id: str):
    data = _load()

    if ig_id in data:
        del data[ig_id]
        _save(data)
        return True

    return False
