import requests
from urllib.parse import quote
from config import INSTAGRAM_ACCESS_TOKEN

GRAPH_API_URL = "https://graph.instagram.com"
BUTTON_TEMPLATE_TEXT_MAX = 640


def _safe_json(response):
    try:
        data = response.json()
    except Exception:
        return {
            "error": {
                "message": "Invalid JSON response",
                "status_code": response.status_code,
                "raw": response.text,
            }
        }

    print("API RESPONSE:", data)
    return data


def _truncate_text(text: str, max_len: int = BUTTON_TEMPLATE_TEXT_MAX) -> str:
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def send_dm(comment_id: str, message: str):
    url = f"{GRAPH_API_URL}/me/messages"
    payload = {
        "recipient": {"comment_id": comment_id},
        "message": {"text": message},
    }
    params = {"access_token": INSTAGRAM_ACCESS_TOKEN}

    try:
        response = requests.post(url, json=payload, params=params, timeout=30)
        return _safe_json(response)
    except requests.RequestException as e:
        return {"error": {"message": f"Failed to send DM: {str(e)}"}}


def send_text_dm_to_user(igsid: str, message: str):
    url = f"{GRAPH_API_URL}/me/messages"
    payload = {
        "recipient": {"id": igsid},
        "message": {"text": message},
    }
    params = {"access_token": INSTAGRAM_ACCESS_TOKEN}

    try:
        response = requests.post(url, json=payload, params=params, timeout=30)
        return _safe_json(response)
    except requests.RequestException as e:
        return {"error": {"message": f"Failed to send text DM to user: {str(e)}"}}


def send_dm_with_button(comment_id: str, text: str, button_label: str, button_url: str):
    url = f"{GRAPH_API_URL}/me/messages"
    safe_text = _truncate_text(text)

    payload = {
        "recipient": {"comment_id": comment_id},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": safe_text,
                    "buttons": [
                        {
                            "type": "web_url",
                            "url": button_url,
                            "title": (button_label or "Open")[:20],
                        }
                    ],
                },
            }
        },
    }
    params = {"access_token": INSTAGRAM_ACCESS_TOKEN}

    try:
        response = requests.post(url, json=payload, params=params, timeout=30)
        data = _safe_json(response)

        if "error" in data:
            print("BUTTON DM FAILED -> FALLBACK TO PLAIN TEXT:", data.get("error"))
            return send_dm(comment_id, safe_text)

        return data
    except requests.RequestException as e:
        return {"error": {"message": f"Failed to send DM with button: {str(e)}"}}


def send_dm_with_postback_button(comment_id: str, text: str, button_label: str, payload_value: str):
    url = f"{GRAPH_API_URL}/me/messages"
    safe_text = _truncate_text(text)

    payload = {
        "recipient": {"comment_id": comment_id},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": safe_text,
                    "buttons": [
                        {
                            "type": "postback",
                            "title": (button_label or "Send me the access")[:20],
                            "payload": payload_value,
                        }
                    ],
                },
            }
        },
    }
    params = {"access_token": INSTAGRAM_ACCESS_TOKEN}

    try:
        response = requests.post(url, json=payload, params=params, timeout=30)
        data = _safe_json(response)

        if "error" in data:
            print("POSTBACK BUTTON DM FAILED -> FALLBACK TO PLAIN TEXT:", data.get("error"))
            return send_dm(comment_id, safe_text)

        return data
    except requests.RequestException as e:
        return {"error": {"message": f"Failed to send DM with postback button: {str(e)}"}}


def send_regular_buttons(igsid: str, text: str, buttons: list):
    url = f"{GRAPH_API_URL}/me/messages"
    safe_text = _truncate_text(text)

    payload = {
        "recipient": {"id": igsid},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": safe_text,
                    "buttons": buttons[:3],
                },
            }
        },
    }
    params = {"access_token": INSTAGRAM_ACCESS_TOKEN}

    try:
        response = requests.post(url, json=payload, params=params, timeout=30)
        data = _safe_json(response)

        if "error" in data:
            print("REGULAR BUTTONS FAILED -> FALLBACK TO PLAIN TEXT:", data.get("error"))
            return send_text_dm_to_user(igsid, safe_text)

        return data
    except requests.RequestException as e:
        return {"error": {"message": f"Failed to send buttons: {str(e)}"}}


def send_regular_buttons_to_comment(comment_id: str, text: str, buttons: list):
    url = f"{GRAPH_API_URL}/me/messages"
    safe_text = _truncate_text(text)

    payload = {
        "recipient": {"comment_id": comment_id},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": safe_text,
                    "buttons": buttons[:3],
                },
            }
        },
    }
    params = {"access_token": INSTAGRAM_ACCESS_TOKEN}

    try:
        response = requests.post(url, json=payload, params=params, timeout=30)
        data = _safe_json(response)

        if "error" in data:
            print("COMMENT BUTTONS FAILED -> FALLBACK TO PLAIN TEXT:", data.get("error"))
            return send_dm(comment_id, safe_text)

        return data
    except requests.RequestException as e:
        return {"error": {"message": f"Failed to send comment buttons: {str(e)}"}}


def send_quick_replies(comment_id: str, text: str, quick_replies: list):
    url = f"{GRAPH_API_URL}/me/messages"
    payload = {
        "recipient": {"comment_id": comment_id},
        "message": {
            "text": text,
            "quick_replies": quick_replies,
        },
    }
    params = {"access_token": INSTAGRAM_ACCESS_TOKEN}

    try:
        response = requests.post(url, json=payload, params=params, timeout=30)
        return _safe_json(response)
    except requests.RequestException as e:
        return {"error": {"message": f"Failed to send quick replies: {str(e)}"}}


def reply_to_comment(comment_id: str, message: str):
    url = f"{GRAPH_API_URL}/{comment_id}/replies"
    payload = {"message": message}
    params = {"access_token": INSTAGRAM_ACCESS_TOKEN}

    try:
        response = requests.post(url, json=payload, params=params, timeout=30)
        return _safe_json(response)
    except requests.RequestException as e:
        return {"error": {"message": f"Failed to reply to comment: {str(e)}"}}


def get_account_media():
    url = f"{GRAPH_API_URL}/me/media"
    params = {
        "access_token": INSTAGRAM_ACCESS_TOKEN,
        "fields": "id,media_type,media_url,thumbnail_url,permalink,caption",
        "limit": 100,
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        data = _safe_json(response)

        if "error" in data:
            return []

        return data.get("data", [])
    except requests.RequestException:
        return []


def get_user_profile(igsid: str):
    url = f"{GRAPH_API_URL}/{igsid}"
    params = {
        "access_token": INSTAGRAM_ACCESS_TOKEN,
        "fields": "name,username,profile_pic",
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        return _safe_json(response)
    except requests.RequestException as e:
        return {"error": {"message": str(e)}}


def get_user_follow_status(igsid: str):
    """
    Try to read whether the Instagram user follows the business account.

    Returns:
    {
        "ok": bool,
        "follows": bool,
        "data": {...} | None,
        "error": {...} | None
    }
    """
    if not igsid:
        return {
            "ok": False,
            "follows": False,
            "data": None,
            "error": {"message": "Missing igsid"},
        }

    url = f"{GRAPH_API_URL}/{igsid}"
    params = {
        "access_token": INSTAGRAM_ACCESS_TOKEN,
        "fields": "id,username,is_user_follow_business,is_business_follow_user",
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        data = _safe_json(response)

        if "error" in data:
            return {
                "ok": False,
                "follows": False,
                "data": None,
                "error": data.get("error", {}),
            }

        follows = bool(data.get("is_user_follow_business", False))
        return {
            "ok": True,
            "follows": follows,
            "data": data,
            "error": None,
        }
    except requests.RequestException as e:
        return {
            "ok": False,
            "follows": False,
            "data": None,
            "error": {"message": f"Failed to fetch follow status: {str(e)}"},
        }


def build_profile_button(username: str, title: str = "Visit Profile"):
    safe_username = (username or "").strip().replace("@", "")

    if safe_username:
        profile_url = f"https://instagram.com/{quote(safe_username)}"
    else:
        profile_url = "https://instagram.com/"

    return {
        "type": "web_url",
        "url": profile_url,
        "title": (title or "Visit Profile")[:20],
    }
