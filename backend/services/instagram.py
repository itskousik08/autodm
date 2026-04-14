import requests
from urllib.parse import quote
from config import INSTAGRAM_ACCESS_TOKEN

GRAPH_API_URL = "https://graph.instagram.com"


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


def send_dm_with_button(comment_id: str, text: str, button_label: str, button_url: str):
    url = f"{GRAPH_API_URL}/me/messages"
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
            print("BUTTON DM FAILED -> FALLBACK TO TEXT")
            return send_dm(comment_id, text)

        return data
    except requests.RequestException as e:
        return {"error": {"message": f"Failed to send DM with button: {str(e)}"}}


def send_dm_with_postback_button(comment_id: str, text: str, button_label: str, payload_value: str):
    """
    Best-effort:
    first card ko box/button style mein bhejne ke liye.
    Agar account/app capability allow kare to postback button render hoga.
    """
    url = f"{GRAPH_API_URL}/me/messages"
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
            print("POSTBACK BUTTON FAILED -> FALLBACK TO TEXT")
            return send_dm(comment_id, text)

        return data
    except requests.RequestException as e:
        return {"error": {"message": f"Failed to send DM with postback button: {str(e)}"}}


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


def send_regular_buttons(igsid: str, text: str, buttons: list):
    url = f"{GRAPH_API_URL}/me/messages"
    payload = {
        "recipient": {"id": igsid},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": text,
                    "buttons": buttons[:3],
                },
            }
        },
    }
    params = {"access_token": INSTAGRAM_ACCESS_TOKEN}

    try:
        response = requests.post(url, json=payload, params=params, timeout=30)
        return _safe_json(response)
    except requests.RequestException as e:
        return {"error": {"message": f"Failed to send buttons: {str(e)}"}}


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


def build_profile_button(username: str, title: str = "Visit Profile"):
    safe_username = (username or "").strip().replace("@", "")

    if safe_username:
        url = f"https://instagram.com/{quote(safe_username)}"
    else:
        url = "https://instagram.com/"

    return {
        "type": "web_url",
        "url": url,
        "title": (title or "Visit Profile")[:20],
    }
