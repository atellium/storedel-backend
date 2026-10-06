import logging

from firebase_admin import messaging

from core.firebase import get_firebase_app


logger = logging.getLogger(__name__)


def send_push_notification(*, token, title, body, data=None):
    if not token:
        logger.info("Skipping push notification because device token is not set.")
        return None

    message_data = {str(key): str(value) for key, value in (data or {}).items()}
    message_data["title"] = str(title)
    message_data["body"] = str(body)

    try:
        get_firebase_app()
        message = messaging.Message(
            token=token,
            data=message_data,
            android=messaging.AndroidConfig(
                priority="high",
            ),
            apns=messaging.APNSConfig(
                headers={
                    "apns-priority": "5",
                    "apns-push-type": "background",
                },
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        content_available=True,
                    ),
                ),
            ),
        )
        return messaging.send(message)
    except Exception:
        logger.exception("Failed to send push notification.")
        return None
