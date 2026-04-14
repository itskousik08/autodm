import json
import os
import copy
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "reels_config.json")


def _default_config():
    return {
        "reels": {},
        "default": {
            "active": True,
            "trigger_mode": "KEYWORD",   # KEYWORD | ANY_COMMENT
            "trigger_keywords": "info",
            "comment_replies": [
                "@{username} Sent you a message! Check it out!",
                "@{username} Check your DMs 📩",
                "@{username} I just sent you a message. Please check!"
            ],
            "require_follow": False,
            "first_dm": {
                "greeting": "Hey there!",
                "text": "Thanks for your interest! Check your DMs.",
                "cta": "Tap below to get access",
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


def _migrate_legacy_config(config: dict) -> dict:
    default = _default_config()

    if not isinstance(config, dict):
        return default

    config.setdefault("reels", {})
    config.setdefault("default", {})
    old_default = config["default"]

    if "trigger_keyword" in old_default and "trigger_keywords" not in old_default:
        old_default["trigger_keywords"] = old_default.pop("trigger_keyword")

    if "dm_message" in old_default and "first_dm" not in old_default:
        old_default["first_dm"] = {
            "greeting": "Hey there!",
            "text": old_default.pop("dm_message"),
            "cta": "Tap below to get access",
            "button_label": "Send me the access",
            "button_link": ""
        }

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
            ] if access.get("access_link") or access.get("button_label") else []
        }

    if "require_follow" not in old_default:
        old_default["require_follow"] = bool(old_default.get("follow_gate", {}).get("enabled", False))

    if "trigger_mode" not in old_default:
        old_default["trigger_mode"] = "KEYWORD"

    config["default"] = _deep_merge(default["default"], old_default)

    migrated_reels = {}
    for media_id, reel_cfg in config.get("reels", {}).items():
        if not isinstance(reel_cfg, dict):
            reel_cfg = {}

        if "trigger_keyword" in reel_cfg and "trigger_keywords" not in reel_cfg:
            reel_cfg["trigger_keywords"] = reel_cfg.pop("trigger_keyword")

        if "dm_message" in reel_cfg and "first_dm" not in reel_cfg:
            reel_cfg["first_dm"] = {
                "greeting": "Hey there!",
                "text": reel_cfg.pop("dm_message"),
                "cta": "Tap below to get access",
                "button_label": "Send me the access",
                "button_link": ""
            }

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
                ] if access.get("access_link") or access.get("button_label") else []
            }

        if "require_follow" not in reel_cfg:
            reel_cfg["require_follow"] = bool(reel_cfg.get("follow_gate", {}).get("enabled", False))

        if "trigger_mode" not in reel_cfg:
            reel_cfg["trigger_mode"] = "KEYWORD"

        migrated_reels[media_id] = _deep_merge(config["default"], reel_cfg)

    config["reels"] = migrated_reels
    return config


def _load_config():
    if not os.path.exists(CONFIG_FILE):
        default_config = _default_config()
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


def get_reel_config(media_id: str):
    config = _load_config()
    reel_config = config["reels"].get(media_id, {})
    return _deep_merge(config["default"], reel_config)


def update_reel_config(media_id: str, new_config: dict):
    config = _load_config()
    existing = config["reels"].get(media_id, {})
    merged = _deep_merge(_deep_merge(config["default"], existing), new_config)
    config["reels"][media_id] = merged
    _save_config(config)
    return merged


def get_random_comment_reply(config: dict, username: str = "") -> str:
    replies = config.get("comment_replies", [])
    if not isinstance(replies, list) or not replies:
        return ""

    chosen = random.choice([r for r in replies if isinstance(r, str) and r.strip()] or [""])
    if not chosen:
        return ""

    safe_username = (username or "user").strip().replace("@", "")
    return chosen.replace("{username}", safe_username)
