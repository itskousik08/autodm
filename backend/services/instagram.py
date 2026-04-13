import requests
from config import INSTAGRAM_ACCESS_TOKEN

GRAPH_API_BASE = "https://graph.facebook.com/v25.0"
IG_GRAPH_BASE = "https://graph.instagram.com"

def _handle_response(response):
    try:
        data = response.json()
    except Exception:
        return {
            "ok": False,
            "status_code": response.status_code,
            "raw": response.text
        }

    return {
        "ok": response.ok,
        "status_code": response.status_code,
        "data": data
    }

# Private reply / DM triggered from comment
def send_dm(comment_id: str, message: str):
    url = f"{GRAPH_API_BASE}/me/messages"
    payload = {
        "recipient": {"comment_id": comment_id},
        "message": {"text": message}
    }
    params = {"access_token": INSTAGRAM_ACCESS_TOKEN}

    response = requests.post(url, json=payload, params=params, timeout=30)
    return _handle_response(response)

# Button template DM
def send_dm_with_button(comment_id: str, text: str, button_label: str, button_url: str):
    url = f"{GRAPH_API_BASE}/me/messages"
    payload = {
        "recipient": {"comment_id": comment_id},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": text,
                    "buttons": [
                        {
                            "type": "web_url",
                            "url": button_url,
                            "title": button_label
                        }
                    ]
                }
            }
        }
    }
    params = {"access_token": INSTAGRAM_ACCESS_TOKEN}

    response = requests.post(url, json=payload, params=params, timeout=30)
    return _handle_response(response)

# Public reply to comment
def reply_to_comment(comment_id: str, message: str):
    url = f"{GRAPH_API_BASE}/{comment_id}/replies"
    payload = {"message": message}
    params = {"access_token": INSTAGRAM_ACCESS_TOKEN}

    response = requests.post(url, json=payload, params=params, timeout=30)
    return _handle_response(response)

# Fetch media
def get_account_media():
    url = f"{IG_GRAPH_BASE}/me/media"
    params = {
        "access_token": INSTAGRAM_ACCESS_TOKEN,
        "fields": "id,media_type,media_url,thumbnail_url,permalink,caption",
        "limit": 100
    }

    response = requests.get(url, params=params, timeout=30)
    result = _handle_response(response)

    if not result["ok"]:
        return result

    data = result["data"]
    return {
        "ok": True,
        "status_code": result["status_code"],
        "data": data.get("data", [])
    }
