import json
import os
from datetime import datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ANALYTICS_FILE = os.path.join(BASE_DIR, "analytics_events.json")


def _load_events():
    if not os.path.exists(ANALYTICS_FILE):
        return []
    try:
        with open(ANALYTICS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_events(events: list):
    with open(ANALYTICS_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2, ensure_ascii=False)


def log_event(event_type: str, status: str = "success", media_id: str = "", comment_id: str = "", username: str = "", igsid: str = "", meta: dict | None = None):
    events = _load_events()
    events.append({
        "event_type": event_type,
        "status": status,
        "media_id": media_id,
        "comment_id": comment_id,
        "username": username,
        "igsid": igsid,
        "meta": meta or {},
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    _save_events(events)


def get_analytics(days: int = 7):
    if days <= 0:
        days = 7

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    events = _load_events()

    total_comments = 0
    total_dm_sent = 0
    total_dm_failed = 0
    total_comment_replies = 0
    total_comment_reply_failed = 0
    total_postbacks = 0
    per_day = {}

    for event in events:
        raw = event.get("created_at")
        try:
            created_at = datetime.fromisoformat(raw)
        except Exception:
            continue

        if created_at < since:
            continue

        day_key = created_at.strftime("%Y-%m-%d")
        if day_key not in per_day:
            per_day[day_key] = {
                "comments": 0,
                "dm_sent": 0,
                "dm_failed": 0,
                "comment_replies": 0,
                "comment_reply_failed": 0,
                "postbacks": 0
            }

        event_type = event.get("event_type")
        if event_type == "comment_received":
            total_comments += 1
            per_day[day_key]["comments"] += 1
        elif event_type == "dm_sent":
            total_dm_sent += 1
            per_day[day_key]["dm_sent"] += 1
        elif event_type == "dm_failed":
            total_dm_failed += 1
            per_day[day_key]["dm_failed"] += 1
        elif event_type == "comment_reply_sent":
            total_comment_replies += 1
            per_day[day_key]["comment_replies"] += 1
        elif event_type == "comment_reply_failed":
            total_comment_reply_failed += 1
            per_day[day_key]["comment_reply_failed"] += 1
        elif event_type == "postback_received":
            total_postbacks += 1
            per_day[day_key]["postbacks"] += 1

    dm_success_rate = round((total_dm_sent / total_comments) * 100, 2) if total_comments else 0
    reply_success_rate = round((total_comment_replies / total_comments) * 100, 2) if total_comments else 0

    return {
        "days": days,
        "total_comments": total_comments,
        "total_dm_sent": total_dm_sent,
        "total_dm_failed": total_dm_failed,
        "total_comment_replies": total_comment_replies,
        "total_comment_reply_failed": total_comment_reply_failed,
        "total_postbacks": total_postbacks,
        "dm_success_rate_percent": dm_success_rate,
        "reply_success_rate_percent": reply_success_rate,
        "per_day": dict(sorted(per_day.items()))
    }
