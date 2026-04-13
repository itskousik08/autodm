import json
import os
import copy

CONFIG_FILE = "reels_config.json"


def _default_config():
    return {
        "reels": {},
        "default": {
            "active": True,
            "trigger_mode": "KEYWORD",   # KEYWORD | ANY_COMMENT
            "trigger_keywords": "info",
            "comment_reply": "Sent you a DM!",
            "first_dm": {
                "greeting": "Hey there!",
                "text": "Thanks for your interest! Check your DMs.",
                "cta": "Tap below to get access",
                "button_label": "Get Access",
                "button_link": "https://yourwebsite.com"
            },
            "follow_gate": {
                "enabled": False,
                "profile_link": "",
                "follow_message": "Almost there! Please visit my profile and tap follow to continue 😁",
                "retry_message": "It looks like you haven't followed yet. Please follow to get access!"
            },
            "access_delivery": {
                "message": "You now have access 🎉",
                "button_label": "Open Access",
                "access_link": "https://yourwebsite.com/access",
                "secondary_text": "Thank you for following!"
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

    # Legacy keys migration
    if "trigger_keyword" in old_default and "trigger_keywords" not in old_default:
        old_default["trigger_keywords"] = old_default.pop("trigger_keyword")

    if "dm_message" in old_default and "first_dm" not in old_default:
        old_default["first_dm"] = {
            "greeting": "Hey there!",
            "text": old_default.pop("dm_message"),
            "cta": "Tap below to get access",
            "button_label": "Get Access",
            "button_link": "https://yourwebsite.com"
        }

    if "trigger_mode" not in old_default:
        old_default["trigger_mode"] = "KEYWORD"

    # Merge default structure
    config["default"] = _deep_merge(default["default"], old_default)

    # Migrate reel-specific configs too
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
                "button_label": "Get Access",
                "button_link": "https://yourwebsite.com"
            }

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
