from fastapi import APIRouter, Request, Query, HTTPException
from config import VERIFY_TOKEN
from services.instagram import (
    send_dm,
    send_dm_with_button,
    send_dm_with_postback_button,
    send_regular_buttons,
    send_text_dm_to_user,
    reply_to_comment,
    build_profile_button,
    get_user_follow_status,
)
from services.config_manager import (
    get_reel_config,
    get_random_comment_reply,
    get_owner_username,
    get_owner_igsid,
)
from services.analytics_manager import log_event
import json
import os
import time

router = APIRouter(prefix="/webhook", tags=["webhook"])

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESSED_FILE = os.path.join(BASE_DIR, "processed_comments.json")
PROCESSED_REPLIES_FILE = os.path.join(BASE_DIR, "processed_comment_replies.json")
FLOW_STATE_FILE = os.path.join(BASE_DIR, "flow_state.json")


def _load_json_file(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _already_processed(comment_id: str) -> bool:
    data = _load_json_file(PROCESSED_FILE, {})
    return comment_id in data


def _mark_processed(comment_id: str):
    data = _load_json_file(PROCESSED_FILE, {})
    data[comment_id] = int(time.time())
    _save_json_file(PROCESSED_FILE, data)


def _already_replied(comment_id: str) -> bool:
    data = _load_json_file(PROCESSED_REPLIES_FILE, {})
    return comment_id in data


def _mark_replied(comment_id: str):
    data = _load_json_file(PROCESSED_REPLIES_FILE, {})
    data[comment_id] = int(time.time())
    _save_json_file(PROCESSED_REPLIES_FILE, data)


def _get_flow_state() -> dict:
    data = _load_json_file(FLOW_STATE_FILE, {})
    return data if isinstance(data, dict) else {}


def _save_flow_state(data: dict):
    _save_json_file(FLOW_STATE_FILE, data)


def _set_user_state(igsid: str, state: dict):
    data = _get_flow_state()
    existing = data.get(igsid, {})
    data[igsid] = {
        **existing,
        **state,
        "updated_at": int(time.time())
    }
    _save_flow_state(data)


def _get_user_state(igsid: str) -> dict:
    return _get_flow_state().get(igsid, {})


def _same_clean_text(a: str, b: str) -> bool:
    return (a or "").strip().replace("@", "").lower() == (b or "").strip().replace("@", "").lower()


def _is_owner_user(username: str = "", igsid: str = "") -> bool:
    owner_username = get_owner_username()
    owner_igsid = get_owner_igsid()

    if owner_username and username and _same_clean_text(username, owner_username):
        return True

    if owner_igsid and igsid and str(igsid).strip() == str(owner_igsid).strip():
        return True

    return False


def _matches_trigger(comment_text: str, config: dict) -> bool:
    trigger_mode = str(config.get("trigger_mode", "KEYWORD")).upper()

    if trigger_mode == "ANY_COMMENT":
        return True

    raw_keywords = config.get("trigger_keywords", "")
    keywords = [kw.strip().lower() for kw in raw_keywords.split(",") if kw.strip()]

    if not keywords:
        return False

    return any(kw in comment_text for kw in keywords)


def _follow_gate_required(config: dict) -> bool:
    return bool(config.get("require_follow")) or bool(config.get("follow_gate", {}).get("enabled", False))


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

    return send_dm_with_postback_button(
        comment_id=comment_id,
        text=text,
        button_label=button_label,
        payload_value="SEND_ACCESS",
    )


def _send_follow_gate_message(igsid: str, config: dict):
    follow_gate = config.get("follow_gate", {})
    text = (
        follow_gate.get("follow_message", "").strip()
        or "Almost there! Please visit my profile and tap follow to continue 😁"
    )
    visit_label = (follow_gate.get("visit_profile_label", "Visit Profile") or "Visit Profile").strip()
    confirm_label = (follow_gate.get("confirm_label", "I'm following ✅") or "I'm following ✅").strip()

    owner_username = get_owner_username()
    if not owner_username:
        print("OWNER USERNAME MISSING: Visit Profile will fallback to instagram.com")

    buttons = [
        build_profile_button(username=owner_username, title=visit_label),
        {
            "type": "postback",
            "title": confirm_label[:20],
            "payload": "I_AM_FOLLOWING",
        },
    ]

    return send_regular_buttons(igsid=igsid, text=text, buttons=buttons)


def _send_follow_gate_retry_message(igsid: str, config: dict):
    follow_gate = config.get("follow_gate", {})
    text = (
        follow_gate.get("retry_message", "").strip()
        or follow_gate.get("follow_message", "").strip()
        or "Please follow first to continue!"
    )
    visit_label = (follow_gate.get("visit_profile_label", "Visit Profile") or "Visit Profile").strip()
    confirm_label = (follow_gate.get("confirm_label", "I'm following ✅") or "I'm following ✅").strip()

    owner_username = get_owner_username()
    if not owner_username:
        print("OWNER USERNAME MISSING: Visit Profile will fallback to instagram.com")

    buttons = [
        build_profile_button(username=owner_username, title=visit_label),
        {
            "type": "postback",
            "title": confirm_label[:20],
            "payload": "I_AM_FOLLOWING",
        },
    ]

    return send_regular_buttons(igsid=igsid, text=text, buttons=buttons)


def _check_user_follows_owner(igsid: str):
    result = get_user_follow_status(igsid)

    print("FOLLOW STATUS RESULT:", result)

    if not result.get("ok"):
        return {
            "ok": False,
            "follows": False,
            "reason": "lookup_failed",
            "error": result.get("error", {}),
            "data": result.get("data"),
        }

    if result.get("follows"):
        return {
            "ok": True,
            "follows": True,
            "reason": "follows",
            "error": None,
            "data": result.get("data"),
        }

    return {
        "ok": True,
        "follows": False,
        "reason": "not_following",
        "error": None,
        "data": result.get("data"),
    }


def _log_follow_check(media_id: str, username: str, igsid: str, follow_check: dict, source: str):
    log_event(
        event_type="follow_check",
        status="success" if follow_check.get("ok") else "failed",
        media_id=media_id,
        username=username,
        igsid=igsid,
        meta={
            "source": source,
            "follows": follow_check.get("follows"),
            "reason": follow_check.get("reason"),
            "error": follow_check.get("error"),
            "data": follow_check.get("data"),
        },
    )


def _normalize_button(btn: dict):
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


def _find_box(config: dict, box_id: str):
    boxes = config.get("main_message", {}).get("boxes", [])
    for box in boxes:
        if not isinstance(box, dict):
            continue
        if (box.get("id") or "").strip() == box_id:
            return box
    return None


def _send_box_message(igsid: str, box: dict):
    text = (box.get("text") or "").strip()
    raw_buttons = box.get("buttons", [])

    buttons = []
    for btn in raw_buttons[:4]:
        normalized = _normalize_button(btn)
        if normalized:
            buttons.append(normalized)

    if buttons:
        return send_regular_buttons(
            igsid=igsid,
            text=text or "Choose an option",
            buttons=buttons[:3],
        )

    return send_text_dm_to_user(igsid, text or "")


def _send_main_message(igsid: str, config: dict):
    main_message = config.get("main_message", {})
    text = (main_message.get("text") or "").strip()
    buttons_raw = main_message.get("buttons", [])

    buttons = []
    for btn in buttons_raw[:4]:
        normalized = _normalize_button(btn)
        if normalized:
            buttons.append(normalized)

    if buttons:
        return send_regular_buttons(
            igsid=igsid,
            text=text or "Here is your access",
            buttons=buttons[:3],
        )

    return send_text_dm_to_user(igsid, text or "Here is your access")


def _send_main_message_to_comment(comment_id: str, config: dict):
    main_message = config.get("main_message", {})
    text = (main_message.get("text") or "").strip() or "Here is your access"
    buttons_raw = main_message.get("buttons", [])

    for btn in buttons_raw[:4]:
        normalized = _normalize_button(btn)
        if not normalized:
            continue

        if normalized.get("type") == "web_url":
            return send_dm_with_button(
                comment_id=comment_id,
                text=text,
                button_label=normalized.get("title") or "Open",
                button_url=normalized.get("url") or "",
            )

        if normalized.get("type") == "postback":
            return send_dm_with_postback_button(
                comment_id=comment_id,
                text=text,
                button_label=normalized.get("title") or "Continue",
                payload_value=normalized.get("payload") or "ACCESS_SENT",
            )

    return send_dm(comment_id=comment_id, message=text)


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("")
async def handle_webhook(request: Request):
    body = await request.json()

    print("WEBHOOK BODY:", body)

    # -------------------------
    # 1. COMMENT EVENTS
    # -------------------------
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

            if _is_owner_user(username=username, igsid=igsid):
                print("OWNER COMMENT SKIPPED:", username, igsid)
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

            log_event(
                event_type="comment_received",
                status="success",
                media_id=media_id,
                comment_id=comment_id,
                username=username,
                igsid=igsid,
            )

            follow_required = _follow_gate_required(config)
            dm_result = None
            state_step = "INITIAL_DM_SENT"
            state_extra = {}

            print("FOLLOW REQUIRED:", follow_required)
            print("COMMENT EVENT IGSID:", igsid)

            if follow_required and igsid:
                follow_check = _check_user_follows_owner(igsid=igsid)
                _log_follow_check(
                    media_id=media_id,
                    username=username,
                    igsid=igsid,
                    follow_check=follow_check,
                    source="comment_precheck",
                )

                if follow_check.get("ok") and follow_check.get("follows"):
                    dm_result = _send_main_message_to_comment(comment_id=comment_id, config=config)
                    state_step = "MAIN_MESSAGE_SENT"
                    state_extra = {
                        "is_following": True,
                        "follow_check_reason": follow_check.get("reason"),
                    }
                else:
                    dm_result = _send_initial_dm(comment_id, config)
                    state_step = "INITIAL_DM_SENT"
                    state_extra = {
                        "is_following": False,
                        "follow_check_reason": follow_check.get("reason"),
                    }
            else:
                dm_result = _send_initial_dm(comment_id, config)

            print("DM RESULT:", dm_result)

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
            else:
                log_event(
                    event_type="dm_sent",
                    status="success",
                    media_id=media_id,
                    comment_id=comment_id,
                    username=username,
                    igsid=canonical_igsid,
                    meta={"step": state_step},
                )

            reply_message = get_random_comment_reply(config, username=username)
            if reply_message:
                if _already_replied(comment_id):
                    print("COMMENT REPLY ALREADY SENT, SKIPPING:", comment_id)
                else:
                    _mark_replied(comment_id)

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
                    "step": state_step,
                    **state_extra,
                })

    # -------------------------
    # 2. MESSAGING / BUTTON CLICK EVENTS
    # -------------------------
    for entry in body.get("entry", []):
        for messaging in entry.get("messaging", []):
            print("MESSAGING EVENT:", messaging)

            sender = messaging.get("sender", {}) or {}
            igsid = (sender.get("id") or "").strip()
            if not igsid:
                continue

            if _is_owner_user(igsid=igsid):
                print("OWNER MESSAGING EVENT SKIPPED:", igsid)
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
            config = get_reel_config(media_id) if media_id else get_reel_config("__default__")

            print("POSTBACK PAYLOAD:", payload)
            print("USER STATE:", state)
            print("FOLLOW REQUIRED:", _follow_gate_required(config))

            log_event(
                event_type="postback_received",
                status="success",
                media_id=media_id,
                username=username,
                igsid=igsid,
                meta={"payload": payload},
            )

            if payload == "SEND_ACCESS":
                if _follow_gate_required(config):
                    follow_check = _check_user_follows_owner(igsid=igsid)
                    _log_follow_check(
                        media_id=media_id,
                        username=username,
                        igsid=igsid,
                        follow_check=follow_check,
                        source="send_access_click",
                    )

                    if follow_check.get("ok") and follow_check.get("follows"):
                        result = _send_main_message(igsid=igsid, config=config)
                        print("MAIN MESSAGE RESULT:", result)

                        _set_user_state(igsid, {
                            "media_id": media_id,
                            "username": username,
                            "step": "MAIN_MESSAGE_SENT",
                            "is_following": True,
                            "follow_check_reason": follow_check.get("reason"),
                        })
                    else:
                        result = _send_follow_gate_message(igsid=igsid, config=config)
                        print("FOLLOW GATE RESULT:", result)

                        _set_user_state(igsid, {
                            "media_id": media_id,
                            "username": username,
                            "step": "FOLLOW_GATE_SENT",
                            "is_following": False,
                            "follow_check_reason": follow_check.get("reason"),
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
                follow_check = _check_user_follows_owner(igsid=igsid)
                _log_follow_check(
                    media_id=media_id,
                    username=username,
                    igsid=igsid,
                    follow_check=follow_check,
                    source="i_am_following_click",
                )

                if follow_check.get("ok") and follow_check.get("follows"):
                    result = _send_main_message(igsid=igsid, config=config)
                    print("FOLLOW CONFIRM RESULT:", result)

                    _set_user_state(igsid, {
                        "media_id": media_id,
                        "username": username,
                        "step": "MAIN_MESSAGE_SENT",
                        "is_following": True,
                        "follow_check_reason": follow_check.get("reason"),
                    })
                else:
                    result = _send_follow_gate_retry_message(igsid=igsid, config=config)
                    print("FOLLOW RETRY RESULT:", result)

                    _set_user_state(igsid, {
                        "media_id": media_id,
                        "username": username,
                        "step": "FOLLOW_GATE_SENT",
                        "is_following": False,
                        "follow_check_reason": follow_check.get("reason"),
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
                    print("BOX NOT FOUND:", box_id)

            elif payload == "ACCESS_SENT":
                print("ACCESS_SENT payload received. No action needed.")

    return {"status": "ok"}
