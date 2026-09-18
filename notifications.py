import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from pywebpush import WebPushException, webpush

try:
    from .database import (
        delete_push_subscription,
        get_pending_vote_reminders,
        get_push_subscriptions,
        mark_notification_delivered,
    )
except ImportError:
    from database import (
        delete_push_subscription,
        get_pending_vote_reminders,
        get_push_subscriptions,
        mark_notification_delivered,
    )

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY")
VAPID_SUBJECT = os.getenv("VAPID_SUBJECT", "mailto:admin@example.com")
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "America/Bogota")


def colombia_today():
    return datetime.now(ZoneInfo(APP_TIMEZONE)).date()


def send_pending_reminders(work_date=None) -> dict:
    if not VAPID_PRIVATE_KEY:
        raise RuntimeError("VAPID_PRIVATE_KEY no está configurada.")

    reminder_date = work_date or colombia_today()
    pending_users = get_pending_vote_reminders(reminder_date)
    result = {
        "work_date": reminder_date.isoformat(),
        "users_with_pending_votes": len(pending_users),
        "sent": 0,
        "failed": 0,
        "expired_removed": 0,
        "details": [],
    }

    for user in pending_users:
        subscriptions = get_push_subscriptions(user["user_id"])
        user_result = {
            "user_id": user["user_id"],
            "user_name": user["user_name"],
            "pending_count": user["pending_count"],
            "devices": len(subscriptions),
            "sent": 0,
        }
        payload = json.dumps({
            "title": "Votación pendiente · PicaRico",
            "body": f"Tienes {user['pending_count']} tarea(s) de tu compañera por evaluar.",
            "url": f"/?page=votacion&date={reminder_date.isoformat()}",
            "tag": f"picarico-vote-{reminder_date.isoformat()}-{user['user_id']}",
        })

        for subscription in subscriptions:
            subscription_info = {
                "endpoint": subscription["endpoint"],
                "keys": {
                    "p256dh": subscription["p256dh"],
                    "auth": subscription["auth"],
                },
            }
            try:
                webpush(
                    subscription_info=subscription_info,
                    data=payload,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": VAPID_SUBJECT},
                    timeout=15,
                )
                result["sent"] += 1
                user_result["sent"] += 1
            except WebPushException as error:
                status_code = getattr(error.response, "status_code", None)
                if status_code in (404, 410):
                    delete_push_subscription(subscription["endpoint"])
                    result["expired_removed"] += 1
                else:
                    result["failed"] += 1
        if user_result["sent"]:
            mark_notification_delivered(user["user_id"], reminder_date)
        result["details"].append(user_result)

    return result
