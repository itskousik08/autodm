from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from services.instagram import get_account_media, send_dm, reply_to_comment
from services.config_manager import get_all_configs, update_reel_config, get_reel_config
from services.analytics_manager import get_analytics

router = APIRouter(prefix="/api", tags=["admin"])


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


class MainMessageButton(BaseModel):
    label: str = ""
    url: str = ""


class MainMessageConfig(BaseModel):
    text: str = ""
    buttons: List[MainMessageButton] = Field(default_factory=list)


class AdvancedConfig(BaseModel):
    delay_first_dm: int = 0
    prevent_duplicate: bool = True


class ReelConfigUpdate(BaseModel):
    active: bool = True
    trigger_mode: str = "KEYWORD"
    trigger_keywords: str = "info"

    # old single comment_reply ki jagah ab multiple random replies
    comment_replies: List[str] = Field(default_factory=list)

    # follow requirement shortcut
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


@router.get("/reels")
async def fetch_reels():
    try:
        media_items = get_account_media()
        configs = get_all_configs()

        reels = []
        for item in media_items:
            media_id = item["id"]
            config = configs["reels"].get(media_id, configs["default"])

            reels.append({
                "id": media_id,
                "thumbnail_url": item.get("thumbnail_url", item.get("media_url")),
                "permalink": item.get("permalink"),
                "caption": item.get("caption", "")[:100],
                "config": config
            })

        return {"reels": reels, "total": len(reels)}
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

        # safe cleanup: blank replies remove
        payload["comment_replies"] = [
            reply.strip()
            for reply in payload.get("comment_replies", [])
            if isinstance(reply, str) and reply.strip()
        ]

        # follow_gate.enabled ko require_follow ke saath sync karo
        if "follow_gate" not in payload or not isinstance(payload["follow_gate"], dict):
            payload["follow_gate"] = {}

        payload["follow_gate"]["enabled"] = bool(payload.get("require_follow", False))

        # main_message buttons max 2 hi rakho
        main_message = payload.get("main_message", {})
        buttons = main_message.get("buttons", [])
        cleaned_buttons = []

        for btn in buttons[:2]:
            if not isinstance(btn, dict):
                continue

            label = (btn.get("label") or "").strip()
            url = (btn.get("url") or "").strip()

            if label and url:
                cleaned_buttons.append({
                    "label": label,
                    "url": url
                })

        payload["main_message"]["buttons"] = cleaned_buttons

        updated = update_reel_config(media_id, payload)
        return {"status": "updated", "media_id": media_id, "config": updated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    try:
        media_items = get_account_media()
        configs = get_all_configs()

        total = len(media_items)
        configured = 0
        using_default = 0

        for item in media_items:
            media_id = item["id"]
            if media_id in configs["reels"]:
                configured += 1
            else:
                using_default += 1

        return {
            "total_reels": total,
            "configured": configured,
            "using_default": using_default
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics")
async def analytics(days: int = 7):
    try:
        if days not in [7, 30]:
            days = 7
        return get_analytics(days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
