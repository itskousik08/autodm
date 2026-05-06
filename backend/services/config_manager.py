import json
import os
import copy
import random
import time
from typing import Optional

try:
    from config import OWNER_USERNAME, OWNER_IGSID
except Exception:
    OWNER_USERNAME = ""
    OWNER_IGSID = ""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "reels_config.json")


def _clean_username(value: str) -> str:
    if not value:
        return ""

    username = str(value).strip().replace('"', "").replace("'", "")
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


def _auto_fetch_owner_profile() -> dict:
    """
    Fetch owner account username automatically using current access token.
    Safe lazy import avoids circular import.
    """
    try:
        from services.instagram import get_business_account_profile
        result = get_business_account_profile()

        if result.get("ok") and result.get("username"):
            return {
                "owner_username": _clean_username(result.get("username")),
                "owner_igsid": "",
                "owner_account_id": str(result.get("id") or ""),
                "auto_fetched": True,
                "auto_fetch_error": "",
                "updated_at": int(time.time()),
            }

        return {
            "owner_username": "",
            "owner_igsid": "",
            "owner_account_id": "",
            "auto_fetched": False,
            "auto_fetch_error": str(result.get("error") or "Could not fetch username"),
            "updated_at": int(time.time()),
        }
    except Exception as e:
        return {
            "owner_username": "",
            "owner_igsid": "",
            "owner_account_id": "",
            "auto_fetched": False,
            "auto_fetch_error": str(e),
            "updated_at": int(time.time()),
        }


def _default_boxes():
    return [
        {
            "id": "box_main",
            "name": "Main Box",
            "text": "Here is your access 🎉",
            "buttons": [
                {
                    "id": "btn_1",
                    "label": "Open Access",
                    "action_type": "url",   # url | goto
                    "url": "https://yourwebsite.com/access",
                    "target_box_id": ""
                }
            ]
        }
    ]


def _default_config():
    owner_username = _clean_username(OWNER_USERNAME)
    settings = {
        "owner_username": owner_username,
        "owner_igsid": (OWNER_IGSID or "").strip(),
        "owner_account_id": "",
        "auto_fetched": False,
        "auto_fetch_error": "",
        "updated_at": int(time.time()),
    }

    return {
        "settings": settings,
        "reels": {},
        "default": {
            "active": True,
            "trigger_mode": "KEYWORD",   # KEYWORD | ANY_COMMENT
            "trigger_keywords": "info",
            "require_follow": False,
            "comment_replies": [
                "@{username} Check your DMs",
                "@{username} Sent you a message! Check it out!",
                "@{username} I sent you a DM"
            ],
            "first_dm": {
                "greeting": "Hey there!",
                "text": "Thanks for your interest!",
                "cta": "Tap below and I’ll send you the access",
                "button_label": "Send me the access",
                "button_link": ""
            },
            "follow_gate": {
                "enabled": False,
                "follow_message": "Almost there! Please visit my profile and tap follow to continue 😁",
                "retry_message": "Please follow first to continue!",
                "visit_profile_label": "Visit Profile",
                "confirm_label": "I'm following ✅"
            },
            "main_message": {
                "text": "Here is your access 🎉",
                "buttons": [
                    {
                        "label": "Open Access",
                        "url": "https://yourwebsite.com/access"
                    }
                ]
            },
            "message_boxes": _default_boxes(),
            "start_box_id": "box_main",
            "advanced": {
                "delay_first_dm": 0,
                "prevent_duplicate": True
            }
        }
    }


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _normalize_buttons(buttons):
    cleaned = []
    for idx, btn in enumerate(buttons or []):
        if not isinstance(btn, dict):
            continue

        action_type = (btn.get("action_type") or "url").strip().lower()
        if action_type not in ["url", "goto"]:
            action_type = "url"

        cleaned.append({
            "id": btn.get("id") or f"btn_{idx+1}",
            "label": (btn.get("label") or "").strip(),
            "action_type": action_type,
            "url": (btn.get("url") or "").strip(),
            "target_box_id": (btn.get("target_box_id") or "").strip()
        })
    return cleaned


def _normalize_boxes(boxes):
    cleaned = []
    for idx, box in enumerate(boxes or []):
        if not isinstance(box, dict):
            continue

        box_id = (box.get("id") or f"box_{idx+1}").strip()
        cleaned.append({
            "id": box_id,
            "name": (box.get("name") or f"Box {idx+1}").strip(),
            "text": (box.get("text") or "").strip(),
            "buttons": _normalize_buttons(box.get("buttons", []))
        })

    if not cleaned:
        cleaned = _default_boxes()

    return cleaned


def _normalize_settings(settings: dict, allow_auto_fetch: bool = True) -> dict:
    if not isinstance(settings, dict):
        settings = {}

    owner_username = _clean_username(settings.get("owner_username") or OWNER_USERNAME or "")
    owner_igsid = (settings.get("owner_igsid") or OWNER_IGSID or "").strip()
    owner_account_id = str(settings.get("owner_account_id") or "").strip()

    normalized = {
        "owner_username": owner_username,
        "owner_igsid": owner_igsid,
        "owner_account_id": owner_account_id,
        "auto_fetched": bool(settings.get("auto_fetched", False)),
        "auto_fetch_error": str(settings.get("auto_fetch_error") or ""),
        "updated_at": int(settings.get("updated_at") or time.time()),
    }

    # Auto-fetch only when username is missing.
    if allow_auto_fetch and not normalized["owner_username"]:
        fetched = _auto_fetch_owner_profile()
        if fetched.get("owner_username"):
            normalized.update(fetched)

    return normalized


def _migrate_legacy_config(config: dict) -> dict:
    default = _default_config()

    if not isinstance(config, dict):
        return default

    config.setdefault("settings", {})
    config["settings"] = _normalize_settings(config.get("settings", {}), allow_auto_fetch=True)

    config.setdefault("reels", {})
    config.setdefault("default", {})
    old_default = config["default"]

    if "trigger_keyword" in old_default and "trigger_keywords" not in old_default:
        old_default["trigger_keywords"] = old_default.pop("trigger_keyword")

    if "comment_reply" in old_default and "comment_replies" not in old_default:
        old_reply = old_default.pop("comment_reply")
        old_default["comment_replies"] = [old_reply] if old_reply else []

    if "access_delivery" in old_default and "main_message" not in old_default:
        access = old_default.pop("access_delivery")
        old_default["main_message"] = {
            "text": access.get("message", "Here is your access 🎉"),
            "buttons": [
                {
                    "label": access.get("button_label", "Open Access"),
                    "url": access.get("access_link", "")
                }
            ] if access.get("button_label") or access.get("access_link") else []
        }

    if "message_boxes" not in old_default:
        main_message = old_default.get("main_message", {})
        old_default["message_boxes"] = [
            {
                "id": "box_main",
                "name": "Main Box",
                "text": main_message.get("text", "Here is your access 🎉"),
                "buttons": [
                    {
                        "id": f"btn_{i+1}",
                        "label": (btn.get("label") or "").strip(),
                        "action_type": "url",
                        "url": (btn.get("url") or "").strip(),
                        "target_box_id": ""
                    }
                    for i, btn in enumerate(main_message.get("buttons", [])[:4])
                    if isinstance(btn, dict) and ((btn.get("label") or "").strip() or (btn.get("url") or "").strip())
                ]
            }
        ]
        old_default["start_box_id"] = "box_main"

    config["default"] = _deep_merge(default["default"], old_default)
    config["default"]["message_boxes"] = _normalize_boxes(config["default"].get("message_boxes", []))
    config["default"]["start_box_id"] = (config["default"].get("start_box_id") or "box_main").strip()

    migrated_reels = {}
    for media_id, reel_cfg in config.get("reels", {}).items():
        if not isinstance(reel_cfg, dict):
            reel_cfg = {}

        if "trigger_keyword" in reel_cfg and "trigger_keywords" not in reel_cfg:
            reel_cfg["trigger_keywords"] = reel_cfg.pop("trigger_keyword")

        if "comment_reply" in reel_cfg and "comment_replies" not in reel_cfg:
            old_reply = reel_cfg.pop("comment_reply")
            reel_cfg["comment_replies"] = [old_reply] if old_reply else []

        if "access_delivery" in reel_cfg and "main_message" not in reel_cfg:
            access = reel_cfg.pop("access_delivery")
            reel_cfg["main_message"] = {
                "text": access.get("message", "Here is your access 🎉"),
                "buttons": [
                    {
                        "label": access.get("button_label", "Open Access"),
                        "url": access.get("access_link", "")
                    }
                ] if access.get("button_label") or access.get("access_link") else []
            }

        merged = _deep_merge(config["default"], reel_cfg)

        if "message_boxes" not in merged or not merged["message_boxes"]:
            main_message = merged.get("main_message", {})
            merged["message_boxes"] = [
                {
                    "id": "box_main",
                    "name": "Main Box",
                    "text": main_message.get("text", "Here is your access 🎉"),
                    "buttons": [
                        {
                            "id": f"btn_{i+1}",
                            "label": (btn.get("label") or "").strip(),
                            "action_type": "url",
                            "url": (btn.get("url") or "").strip(),
                            "target_box_id": ""
                        }
                        for i, btn in enumerate(main_message.get("buttons", [])[:4])
                        if isinstance(btn, dict) and ((btn.get("label") or "").strip() or (btn.get("url") or "").strip())
                    ]
                }
            ]
            merged["start_box_id"] = "box_main"

        merged["message_boxes"] = _normalize_boxes(merged.get("message_boxes", []))
        merged["start_box_id"] = (merged.get("start_box_id") or "box_main").strip()

        migrated_reels[media_id] = merged

    config["reels"] = migrated_reels
    return config


def _load_config():
    if not os.path.exists(CONFIG_FILE):
        default_config = _default_config()
        default_config["settings"] = _normalize_settings(default_config.get("settings", {}), allow_auto_fetch=True)
        _save_config(default_config)
        return default_config

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError):
        config = _default_config()

    config = _migrate_legacy_config(config)
    _save_config(config)
    return config


def _save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_all_configs():
    return _load_config()


def get_global_settings():
    config = _load_config()
    return config.get("settings", {})


def update_global_settings(new_settings: dict):
    config = _load_config()

    existing = config.get("settings", {})
    merged = {
        **existing,
        **(new_settings or {}),
    }

    # If frontend sends empty username intentionally, auto-fetch again.
    config["settings"] = _normalize_settings(merged, allow_auto_fetch=True)
    _save_config(config)
    return config["settings"]


def refresh_global_settings_from_instagram():
    config = _load_config()
    fetched = _auto_fetch_owner_profile()

    if fetched.get("owner_username"):
        config["settings"] = _normalize_settings({
            **config.get("settings", {}),
            **fetched,
        }, allow_auto_fetch=False)
        _save_config(config)

    return config.get("settings", {})


def get_owner_username() -> str:
    settings = get_global_settings()
    return _clean_username(settings.get("owner_username") or OWNER_USERNAME or "")


def get_owner_igsid() -> str:
    settings = get_global_settings()
    return (settings.get("owner_igsid") or OWNER_IGSID or "").strip()


def get_reel_config(media_id: str):
    config = _load_config()
    reel_config = config["reels"].get(media_id, {})
    return _deep_merge(config["default"], reel_config)


def update_reel_config(media_id: str, new_config: dict):
    config = _load_config()
    existing = config["reels"].get(media_id, {})
    merged = _deep_merge(_deep_merge(config["default"], existing), new_config)

    merged["comment_replies"] = list(dict.fromkeys([
        r.strip()
        for r in merged.get("comment_replies", [])
        if isinstance(r, str) and r.strip()
    ]))

    merged["message_boxes"] = _normalize_boxes(merged.get("message_boxes", []))
    merged["start_box_id"] = (merged.get("start_box_id") or "box_main").strip()

    config["reels"][media_id] = merged
    _save_config(config)
    return merged


def get_random_comment_reply(config: dict, username: str = "") -> str:
    replies = config.get("comment_replies", [])
    if not isinstance(replies, list) or not replies:
        return ""

    clean_replies = list(dict.fromkeys([
        r.strip() for r in replies
        if isinstance(r, str) and r.strip()
    ]))

    chosen = random.choice(clean_replies or [""])
    if not chosen:
        return ""

    safe_username = (username or "user").strip().replace("@", "")
    return chosen.replace("{username}", safe_username)


def get_box_by_id(config: dict, box_id: str) -> Optional[dict]:
    for box in config.get("message_boxes", []):
        if isinstance(box, dict) and box.get("id") == box_id:
            return box
    return None


def get_start_box(config: dict) -> Optional[dict]:
    start_box_id = (config.get("start_box_id") or "").strip()
    box = get_box_by_id(config, start_box_id)
    if box:
        return box

    boxes = config.get("message_boxes", [])
    if boxes:
        return boxes[0]
    return None
