from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.auth import get_current_user
from app.database import DatabaseManager

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

class AlertSettingsUpdate(BaseModel):
    channel: str = "browser"                # telegram, email, browser
    materiality_threshold: str = "high"    # high, medium
    telegram_chat_id: Optional[str] = ""
    email_destination: Optional[str] = ""
    enabled: bool = True

def get_user_id(user: dict) -> str:
    user_id = user.get("sub") or user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in token")
    return user_id

@router.get("/settings")
def get_alert_settings(user: dict = Depends(get_current_user)):
    """Fetch user alert notification preferences."""
    user_id = get_user_id(user)
    return DatabaseManager.get_alert_settings(user_id)

@router.post("/settings")
def update_alert_settings(payload: AlertSettingsUpdate, user: dict = Depends(get_current_user)):
    """Update user alert channel and materiality threshold preferences."""
    user_id = get_user_id(user)
    settings_dict = payload.dict()
    updated = DatabaseManager.save_alert_settings(user_id, settings_dict)
    return updated

@router.get("/history")
def get_alert_history(user: dict = Depends(get_current_user)):
    """Fetch history of high-materiality alerts dispatched to user."""
    user_id = get_user_id(user)
    history = DatabaseManager.get_sent_alerts(user_id)
    return {
        "count": len(history),
        "history": history
    }
