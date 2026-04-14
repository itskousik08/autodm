from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services.instagram import get_account_media, send_dm, reply_to_comment
from services.config_manager import get_all_configs, update_reel_config, get_reel_config
from services.analytics_manager import get_analytics, get_logs, cleanup_old_logs

router = APIRouter(prefix="/api", tags=["admin"])


# =========================
# Pydantic Models
# =========================

class FirstDMConfig(BaseModel):
    greeting: str = ""
    text: str = ""
    cta: str = ""
    button_label: str = "Send me the access"
    button_link: str = ""


class FollowGateConfig(BaseModel):
    enabled: bool = False
    follow_message: str = "Almost there! Please visit my profile and tap follow to continue 😁"
    retry_message: str = "Please follow first to continue!"
    visit_profile_label: str = "Visit Profile"
    confirm_label: str = "I'm following ✅"


class FlowButton(BaseModel):
    label: str = ""
    url: str = ""
    action_type: str = "link"   # "link" | "next_box"
    next_box_id: str = ""


class MessageBoxConfig(BaseModel):
    id: str = ""
    title: str = ""
    text: str = ""
    buttons: List[FlowButton] = Field(default_factory=list)


class MainMessageConfig(BaseModel):
    text: str = ""
    buttons: List[FlowButton] = Field(default_factory=list)
    boxes: List[MessageBoxConfig] = Field(default_factory=list)


class AdvancedConfig(BaseModel):
    delay_first_dm: int = 0
    prevent_duplicate: bool = True


class ReelConfigUpdate(BaseModel):
    active: bool = True
    trigger_mode: str = "KEYWORD"
    trigger_keywords: str = "info"
    comment_replies: List[str] = Field(default_factory=list)

    require_follow: bool = False

    first_dm: FirstDMConfig = Field(default_factory=FirstDMConfig)
    follow_gate: FollowGateConfig = Field(default_factory=FollowGateConfig)
    main_message: MainMessageConfig = Field(default_factory=MainMessageConfig)
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)


class TestDMRequest(BaseModel):
    comment_id: str
    message: str


class TestReplyRequest(BaseModel):
    comment_id: str
    message: str


# =========================
# Reels
# =========================

@router.get("/reels")
async def fetch_reels():
    try:
        media_items = get_account_media()
        configs = get_all_configs()

        reels = []
        for item in media_items:
            media_id = item.get("id")
            if not media_id:
                continue

            config = configs.get("reels", {}).get(media_id, configs.get("default", {}))

            reels.append({
                "id": media_id,
                "thumbnail_url": item.get("thumbnail_url") or item.get("media_url"),
                "permalink": item.get("permalink"),
                "caption": (item.get("caption") or "")[:120],
                "media_type": item.get("media_type"),
                "config": config,
            })

        return {
            "reels": reels,
            "total": len(reels),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reels/{media_id}")
async def get_reel(media_id: str):
    try:
        config = get_reel_config(media_id)
        return {"media_id": media_id, "config": config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/reels/{media_id}")
async def update_reel(media_id: str, config: ReelConfigUpdate):
    try:
        payload = config.dict()

        # clean comment replies
        payload["comment_replies"] = [
            r.strip() for r in payload.get("comment_replies", [])
            if isinstance(r, str) and r.strip()
        ]

        # sync require_follow -> follow_gate.enabled
        payload["follow_gate"]["enabled"] = bool(payload.get("require_follow", False))

        # normalize main buttons
        main_buttons = []
        for btn in payload.get("main_message", {}).get("buttons", []):
            if not isinstance(btn, dict):
                continue

            label = (btn.get("label") or "").strip()
            action_type = (btn.get("action_type") or "link").strip()
            url = (btn.get("url") or "").strip()
            next_box_id = (btn.get("next_box_id") or "").strip()

            if not label:
                continue

            if action_type == "link" and not url:
                continue

            if action_type == "next_box" and not next_box_id:
                continue

            main_buttons.append({
                "label": label,
                "url": url,
                "action_type": action_type,
                "next_box_id": next_box_id,
            })

        payload["main_message"]["buttons"] = main_buttons[:4]

        # normalize boxes
        cleaned_boxes = []
        for box in payload.get("main_message", {}).get("boxes", []):
            if not isinstance(box, dict):
                continue

            box_id = (box.get("id") or "").strip()
            title = (box.get("title") or "").strip()
            text = (box.get("text") or "").strip()

            cleaned_buttons = []
            for btn in box.get("buttons", []):
                if not isinstance(btn, dict):
                    continue

                label = (btn.get("label") or "").strip()
                action_type = (btn.get("action_type") or "link").strip()
                url = (btn.get("url") or "").strip()
                next_box_id = (btn.get("next_box_id") or "").strip()

                if not label:
                    continue

                if action_type == "link" and not url:
                    continue

                if action_type == "next_box" and not next_box_id:
                    continue

                cleaned_buttons.append({
                    "label": label,
                    "url": url,
                    "action_type": action_type,
                    "next_box_id": next_box_id,
                })

            if box_id and (text or cleaned_buttons):
                cleaned_boxes.append({
                    "id": box_id,
                    "title": title,
                    "text": text,
                    "buttons": cleaned_buttons[:4],
                })

        payload["main_message"]["boxes"] = cleaned_boxes

        updated = update_reel_config(media_id, payload)
        return {
            "status": "updated",
            "media_id": media_id,
            "config": updated,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# Stats / Analytics
# =========================

@router.get("/stats")
async def get_stats():
    try:
        media_items = get_account_media()
        configs = get_all_configs()

        total = len(media_items)
        configured = 0
        using_default = 0

        for item in media_items:
            media_id = item.get("id")
            if not media_id:
                continue

            if media_id in configs.get("reels", {}):
                configured += 1
            else:
                using_default += 1

        return {
            "total_reels": total,
            "configured": configured,
            "using_default": using_default,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics")
async def analytics(days: int = Query(default=7)):
    try:
        if days not in [7, 30]:
            days = 7
        return get_analytics(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# Logs
# =========================

@router.get("/logs")
async def logs(
    limit: int = Query(default=50, ge=1, le=500),
    event_type: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    username: Optional[str] = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
):
    try:
        return {
            "logs": get_logs(
                limit=limit,
                event_type=event_type,
                status=status,
                username=username,
                days=days,
            )
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logs/cleanup")
async def logs_cleanup(days: int = Query(default=30, ge=1, le=365)):
    try:
        deleted_count = cleanup_old_logs(days=days)
        return {
            "status": "success",
            "deleted_count": deleted_count,
            "kept_days": days,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# Test helpers
# =========================

@router.post("/test/send-dm")
async def test_send_dm(request: TestDMRequest):
    try:
        result = send_dm(request.comment_id, request.message)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test/reply-comment")
async def test_reply_comment(request: TestReplyRequest):
    try:
        result = reply_to_comment(request.comment_id, request.message)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
