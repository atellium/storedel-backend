from django.core.cache import cache
from django.conf import settings
from django.db import connection
from firebase_admin import exceptions, messaging
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from core.firebase import get_firebase_app


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([])
def health(request):
    return Response({"status": "ok"})


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([])
def readiness(request):
    checks = {"database": False, "cache": False}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            checks["database"] = cursor.fetchone() == (1,)
    except Exception:
        pass
    try:
        cache_key = "health:readiness"
        cache.set(cache_key, "ok", timeout=10)
        checks["cache"] = cache.get(cache_key) == "ok"
    except Exception:
        pass
    ready = all(checks.values())
    return Response(
        {"status": "ok" if ready else "unavailable", "checks": checks},
        status=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_device_notification(request):
    token = request.data.get("token") or settings.FCM_STATIC_DEVICE_TOKEN
    data = request.data.get("data", {})

    if not token:
        return Response(
            {
                "detail": (
                    "Provide token in the request body or set "
                    "FCM_STATIC_DEVICE_TOKEN in the environment."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not isinstance(data, dict):
        return Response(
            {"detail": "data must be an object with string-compatible values."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    title = request.data.get("title") or data.get("title") or "Storedel"
    body = (
        request.data.get("body")
        or data.get("body")
        or "You have a new notification."
    )
    message_data = {str(key): str(value) for key, value in data.items()}
    message_data["title"] = str(title)
    message_data["body"] = str(body)

    try:
        get_firebase_app()
        message = messaging.Message(
            token=token,
            data=message_data,
        )
        message_id = messaging.send(message)
    except exceptions.FirebaseError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response(
        {
            "message": "Notification sent successfully.",
            "firebase_message_id": message_id,
            "sent_data": message_data,
        }
    )
