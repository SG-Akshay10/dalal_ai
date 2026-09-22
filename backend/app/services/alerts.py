import os
import logging
import httpx
from typing import List, Dict, Any
from app.database import DatabaseManager

logger = logging.getLogger("alerts_service")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

def send_telegram_message(chat_id: str, text: str) -> bool:
    """Dispatches a message via Telegram Bot API if bot token and chat ID are provided."""
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, json=payload)
            return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Telegram dispatch exception: {e}")
        return False

def evaluate_and_dispatch_alerts(user_id: str, new_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Evaluates newly ingested news items against the user's alert configuration
    and dispatches high/medium materiality alerts.
    """
    settings = DatabaseManager.get_alert_settings(user_id)
    if not settings.get("enabled", True):
        return []

    channel = settings.get("channel", "browser")
    threshold = settings.get("materiality_threshold", "high").lower()
    telegram_chat_id = settings.get("telegram_chat_id", "")

    sent_records = []

    for item in new_items:
        item_mat = str(item.get("materiality", "low")).lower()
        should_alert = False

        if threshold == "high" and item_mat == "high":
            should_alert = True
        elif threshold == "medium" and item_mat in ["high", "medium"]:
            should_alert = True

        if should_alert:
            sym = item.get("symbol", "STOCK")
            title = item.get("title", "")
            summary = item.get("summary", "")
            mat_emoji = "🚨" if item_mat == "high" else "⚠️"

            msg_text = (
                f"{mat_emoji} *HIGH MATERIALITY ALERT: {sym}*\n\n"
                f"*Title:* {title}\n"
                f"*Category:* {item.get('category', 'General News')}\n"
                f"*Sentiment:* {item.get('sentiment', 'neutral').upper()}\n\n"
                f"*AI Summary:* {summary}"
            )

            status = "delivered"
            if channel == "telegram" and telegram_chat_id:
                success = send_telegram_message(telegram_chat_id, msg_text)
                status = "sent_telegram" if success else "failed_telegram"

            record = DatabaseManager.log_sent_alert(user_id, item["id"], channel, status)
            record["item"] = item
            sent_records.append(record)

    return sent_records
