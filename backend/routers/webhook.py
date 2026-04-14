from fastapi import APIRouter, Request, Query, HTTPException
from config import VERIFY_TOKEN
from services.instagram import (
    send_dm_with_button,
    send_dm_with_postback_button,
    send_regular_buttons,
    send_text_dm_to_user,
    reply_to_comment,
    build_profile_button,
)
from services.config_manager import get_reel_config, get_random_comment_reply
from services.analytics_manager import log_event
import json
import os
import time

router = APIRouter(prefix="/webhook", tags=["webhook"])

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESSED_FILE = os.path.join(BASE_DIR, "processed_comments.json")
FLOW_STATE_FILE = os.path.join(BASE_DIR, "flow_state.json")
DELIVERY_STATE_FILE = os.path.join(BASE_DIR, "delivery_state.json")

OWNER_USERNAME = os.getenv("OWNER_IG_USERNAME", "mrkousikai")
FOLLOW_GATE_MAX_ATTEMPTS = 2


# =========================================================
# JSON HELPERS
# =========================================================
def _load_json_file(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json_file(path, data):
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


# =========================================================
# DUPLICATE COMMENT PROTECTION
# =========================================================
def _already_processed(comment_id: str) -> bool:
    data = _load_json_file(PROCESSED_FILE, {})
    return comment_id in data


def _mark_processed(comment_id: str):
    data = _load_json_file(PROCESSED_FILE, {})
    data[comment_id] = int(time.time())
    _save_json_file(PROCESSED_FILE, data)


# =========================================================
# FLOW STATE
# =========================================================
def _get_flow_state() -> dict:
    data = _load_json_file(FLOW_STATE_FILE, {})
    return data if isinstance(data, dict) else {}


def _save_flow_state(data: dict):
    _save_json_file(FLOW_STATE_FILE, data)


def _set_user_state(igsid: str, state: dict):
    all_states = _get_flow_state()
    existing = all_states.get(igsid, {})
    all_states[igsid] = {
        **existing,
        **state,
        "updated_at": int(time.time()),
    }
    _save_flow_state(all_states)


def _get_user_state(igsid: str) -> dict:
    return _get_flow_state().get(igsid, {})


# =========================================================
# DELIVERY STATE
# same user + same media dedupe for DM
# =========================================================
def _delivery_key(media_id: str, username: str) -> str:
    return f"{media_id}::{(username or '').strip().lower()}"


def _get_delivery_state() -> dict:
    data = _load_json_file(DELIVERY_STATE_FILE, {})
    return data if isinstance(data, dict) else {}


def _get_delivery_record(media_id: str, username: str) -> dict:
    data = _get_delivery_state()
    return data.get(_delivery_key(media_id, username), {})


def _set_delivery_record(media_id: str, username: str, record: dict):
    data = _get_delivery_state()
    key = _delivery_key(media_id, username)
    existing = data.get(key, {})
    data[key] = {
        **existing,
        **record,
        "updated_at": int(time.time()),
    }
    _save_json_file(DELIVERY_STATE_FILE, data)


# =========================================================
# LOGIC HELPERS
# =========================================================
def _matches_trigger(comment_text: str, config: dict) -> bool:
    trigger_mode = str(config.get("trigger_mode", "KEYWORD")).upper()

    if trigger_mode == "ANY_COMMENT":
        return True

    raw_keywords = config.get("trigger_keywords", "")
    keywords = [kw.strip().lower() for kw in raw_keywords.split(",") if kw.strip()]

    if not keywords:
        return False

    return any(kw in comment_text for kw in keywords)


def _build_first_dm_text(config: dict) -> str:
    first_dm = config.get("first_dm", {})
    parts = [
        first_dm.get("greeting", "").strip(),
        first_dm.get("text", "").strip(),
        first_dm.get("cta", "").strip(),
    ]
    return "\n\n".join([p for p in parts if p]).strip()


def _send_initial_dm(comment_id: str, config: dict):
    text = _build_first_dm_text(config)
    if not text:
        return {"error": {"message": "Empty DM text"}}

    first_dm = config.get("first_dm", {})
    button_label = (first_dm.get("button_label") or "Send me the access").strip()
    button_link = (first_dm.get("button_link") or "").strip()

    # direct URL button if configured
    if button_link:
        return send_dm_with_button(
            comment_id=comment_id,
            text=text,
            button_label=button_label,
            button_url=button_link,
        )

    # otherwise postback button for next-step flow
    return send_dm_with_postback_button(
        comment_id=comment_id,
        text=text,
        button_label=button_label,
        payload_value="SEND_ACCESS",
    )


def _send_follow_gate_message(igsid: str, config: dict, use_retry_text: bool = False):
    follow_gate = config.get("follow_gate", {})

    follow_text = (
        follow_gate.get("follow_message", "").strip()
        or "Almost there! Please visit my profile and tap follow to continue 😁"
    )
    retry_text = (
        follow_gate.get("retry_message", "").strip()
        or follow_text
    )

    visit_label = (follow_gate.get("visit_profile_label", "Visit Profile") or "Visit Profile").strip()
    confirm_label = (follow_gate.get("confirm_label", "I'm following ✅") or "I'm following ✅").strip()

    text = retry_text if use_retry_text else follow_text

    buttons = [
        build_profile_button(username=OWNER_USERNAME, title=visit_label),
        {
            "type": "postback",
            "title": confirm_label[:20],
            "payload": "I_AM_FOLLOWING",
        },
    ]

    return send_regular_buttons(igsid=igsid, text=text, buttons=buttons)


def _normalize_box_button(btn: dict) -> dict | None:
    if not isinstance(btn, dict):
        return None

    label = (btn.get("label") or "").strip()
    if not label:
        return None

    action_type = (btn.get("action_type") or "link").strip().lower()
    url = (btn.get("url") or "").strip()
    next_box_id = (btn.get("next_box_id") or "").strip()

    if action_type == "next_box":
        if not next_box_id:
            return None
        return {
            "type": "postback",
            "title": label[:20],
            "payload": f"BOX::{next_box_id}",
        }

    if action_type == "link":
        if not url:
            return None
        return {
            "type": "web_url",
            "title": label[:20],
            "url": url,
        }

    return None


def _send_box_message(igsid: str, box: dict):
    text = (box.get("text") or "").strip()
    raw_buttons = box.get("buttons", [])

    buttons = []
    for btn in raw_buttons[:4]:
        normalized = _normalize_box_button(btn)
        if normalized:
            buttons.append(normalized)

    if buttons:
        return send_regular_buttons(
            igsid=igsid,
            text=text or "Choose an option",
            buttons=buttons[:3],  # IG max 3 buttons in template
        )

    return send_text_dm_to_user(igsid, text or "")


def _find_box(config: dict, box_id: str) -> dict | None:
    boxes = config.get("main_message", {}).get("boxes", [])
    for box in boxes:
        if not isinstance(box, dict):
            continue
        if (box.get("id") or "").strip() == box_id:
            return box
    return None


def _send_main_message(igsid: str, config: dict):
    main_message = config.get("main_message", {})
    text = (main_message.get("text") or "").strip()
    raw_buttons = main_message.get("buttons", [])

    buttons = []
    for btn in raw_buttons[:4]:
        normalized = _normalize_box_button(btn)
        if normalized:
            buttons.append(normalized)

    if buttons:
        return send_regular_buttons(
            igsid=igsid,
            text=text or "Here is your access",
            buttons=buttons[:3],
        )

    return send_text_dm_to_user(igsid, text or "Here is your access")


# =========================================================
# WEBHOOK VERIFY
# =========================================================
@router.get("")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


# =========================================================
# MAIN WEBHOOK
# =========================================================
@router.post("")
async def handle_webhook(request: Request):
    body = await request.json()
    print("WEBHOOK BODY:", body)

    # -----------------------------------------------------
    # 1. COMMENT EVENTS
    # -----------------------------------------------------
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "comments":
                continue

            value = change.get("value", {})
            comment_id = value.get("id")
            comment_text = (value.get("text") or "").strip().lower()
            media_id = value.get("media", {}).get("id")

            username = (
                value.get("username")
                or value.get("from", {}).get("username")
                or "user"
            ).strip()

            igsid = (value.get("from", {}).get("id") or "").strip()

            if not comment_id or not media_id:
                continue

            if username.lower() == OWNER_USERNAME.lower():
                _mark_processed(comment_id)
                continue

            if _already_processed(comment_id):
                continue

            config = get_reel_config(media_id)

            if not config.get("active", False):
                _mark_processed(comment_id)
                continue

            if not _matches_trigger(comment_text, config):
                _mark_processed(comment_id)
                continue

            _mark_processed(comment_id)

            delivery_record = _get_delivery_record(media_id, username)
            dm_already_sent = bool(delivery_record.get("dm_sent", False))

            log_event(
                event_type="comment_received",
                status="success",
                media_id=media_id,
                comment_id=comment_id,
                username=username,
                igsid=igsid,
            )

            canonical_igsid = igsid
            dm_result = None

            # Same user + same reel -> DM only once
            # but if previous attempt failed, retry
            if not dm_already_sent:
                dm_result = _send_initial_dm(comment_id, config)
                print("INITIAL DM RESULT:", dm_result)

                canonical_igsid = (dm_result.get("recipient_id") or igsid or "").strip()

                if "error" in dm_result:
                    log_event(
                        event_type="dm_failed",
                        status="failed",
                        media_id=media_id,
                        comment_id=comment_id,
                        username=username,
                        igsid=canonical_igsid,
                        meta=dm_result.get("error", {}),
                    )
                    _set_delivery_record(media_id, username, {
                        "dm_sent": False,
                        "last_comment_id": comment_id,
                        "igsid": canonical_igsid,
                    })
                else:
                    log_event(
                        event_type="dm_sent",
                        status="success",
                        media_id=media_id,
                        comment_id=comment_id,
                        username=username,
                        igsid=canonical_igsid,
                    )
                    _set_delivery_record(media_id, username, {
                        "dm_sent": True,
                        "last_comment_id": comment_id,
                        "igsid": canonical_igsid,
                    })
            else:
                print(f"DM already sent earlier for media={media_id}, user={username}; skipping DM")
                canonical_igsid = (delivery_record.get("igsid") or igsid or "").strip()

            # Comment reply can still go on every valid comment
            reply_message = get_random_comment_reply(config, username=username)
            if reply_message:
                uses_placeholder = any(
                    isinstance(r, str) and "{username}" in r
                    for r in config.get("comment_replies", [])
                )
                final_reply = reply_message if uses_placeholder else f"@{username} {reply_message}"

                reply_result = reply_to_comment(comment_id, final_reply)
                print("COMMENT REPLY RESULT:", reply_result)

                if "error" in reply_result:
                    log_event(
                        event_type="comment_reply_failed",
                        status="failed",
                        media_id=media_id,
                        comment_id=comment_id,
                        username=username,
                        igsid=canonical_igsid,
                        meta=reply_result.get("error", {}),
                    )
                else:
                    log_event(
                        event_type="comment_reply_sent",
                        status="success",
                        media_id=media_id,
                        comment_id=comment_id,
                        username=username,
                        igsid=canonical_igsid,
                        meta={"reply_message": final_reply},
                    )

            if canonical_igsid:
                _set_user_state(canonical_igsid, {
                    "media_id": media_id,
                    "username": username,
                    "step": "INITIAL_DM_SENT",
                    "follow_attempt_count": 0,
                })

    # -----------------------------------------------------
    # 2. MESSAGING / BUTTON CLICK EVENTS
    # -----------------------------------------------------
    for entry in body.get("entry", []):
        for messaging in entry.get("messaging", []):
            print("MESSAGING EVENT:", messaging)

            sender = messaging.get("sender", {}) or {}
            igsid = (sender.get("id") or "").strip()
            if not igsid:
                continue

            payload = None

            postback = messaging.get("postback")
            if isinstance(postback, dict):
                payload = postback.get("payload")

            if not payload:
                quick_reply = (messaging.get("message", {}) or {}).get("quick_reply", {})
                if isinstance(quick_reply, dict):
                    payload = quick_reply.get("payload")

            if not payload:
                continue

            state = _get_user_state(igsid)
            media_id = state.get("media_id", "")
            username = state.get("username", "user")
            follow_attempt_count = int(state.get("follow_attempt_count", 0))

            config = get_reel_config(media_id) if media_id else get_reel_config("__default__")

            print("POSTBACK PAYLOAD:", payload)
            print("USER STATE:", state)

            log_event(
                event_type="postback_received",
                status="success",
                media_id=media_id,
                username=username,
                igsid=igsid,
                meta={"payload": payload},
            )

            if payload == "SEND_ACCESS":
                if bool(config.get("require_follow")) or bool(config.get("follow_gate", {}).get("enabled", False)):
                    result = _send_follow_gate_message(
                        igsid=igsid,
                        config=config,
                        use_retry_text=False,
                    )
                    print("FOLLOW GATE RESULT:", result)

                    _set_user_state(igsid, {
                        "media_id": media_id,
                        "username": username,
                        "step": "FOLLOW_GATE_SENT",
                        "follow_attempt_count": 0,
                    })
                else:
                    result = _send_main_message(igsid=igsid, config=config)
                    print("MAIN MESSAGE RESULT:", result)

                    _set_user_state(igsid, {
                        "media_id": media_id,
                        "username": username,
                        "step": "MAIN_MESSAGE_SENT",
                    })

            elif payload == "I_AM_FOLLOWING":
                new_attempt_count = follow_attempt_count + 1
                print(f"FOLLOW ATTEMPT: {new_attempt_count}/{FOLLOW_GATE_MAX_ATTEMPTS}")

                if new_attempt_count < FOLLOW_GATE_MAX_ATTEMPTS:
                    result = _send_follow_gate_message(
                        igsid=igsid,
                        config=config,
                        use_retry_text=True,
                    )
                    print("FOLLOW RETRY RESULT:", result)

                    _set_user_state(igsid, {
                        "media_id": media_id,
                        "username": username,
                        "step": "FOLLOW_GATE_RETRY",
                        "follow_attempt_count": new_attempt_count,
                    })
                else:
                    result = _send_main_message(igsid=igsid, config=config)
                    print("FOLLOW CONFIRM RESULT:", result)

                    _set_user_state(igsid, {
                        "media_id": media_id,
                        "username": username,
                        "step": "MAIN_MESSAGE_SENT",
                        "follow_attempt_count": new_attempt_count,
                    })

            elif payload.startswith("BOX::"):
                box_id = payload.split("BOX::", 1)[1].strip()
                box = _find_box(config, box_id)

                if box:
                    result = _send_box_message(igsid=igsid, box=box)
                    print("BOX MESSAGE RESULT:", result)

                    _set_user_state(igsid, {
                        "media_id": media_id,
                        "username": username,
                        "step": f"BOX::{box_id}",
                        "current_box_id": box_id,
                    })
                else:
                    print(f"BOX NOT FOUND: {box_id}")

    return {"status": "ok"}
