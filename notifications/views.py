from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from notifications.models import DeviceToken
from notifications.serializers import (
    DeviceTokenRegisterSerializer,
    DeviceTokenSerializer,
    DeviceTokenUnregisterSerializer,
)


def _apply_registration(device_token, user, attrs):
    device_token.user = user
    device_token.device_id = attrs["device_id"]
    device_token.token = attrs["token"]
    device_token.platform = attrs["platform"]
    device_token.browser = attrs.get("browser", "")
    device_token.os = attrs.get("os", "")
    device_token.app_version = attrs.get("app_version", "")
    device_token.is_active = True
    device_token.failure_count = 0
    device_token.last_seen_at = timezone.now()
    device_token.save()
    return device_token


def _register_device_token(user, attrs):
    with transaction.atomic():
        token_record = (
            DeviceToken.objects.select_for_update()
            .filter(token=attrs["token"])
            .first()
        )
        device_record = (
            DeviceToken.objects.select_for_update()
            .filter(user=user, device_id=attrs["device_id"])
            .first()
        )

        if token_record and device_record and token_record.pk != device_record.pk:
            device_record.delete()
            device_token = token_record
        else:
            device_token = token_record or device_record or DeviceToken()

        return _apply_registration(device_token, user, attrs)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def register(request):
    serializer = DeviceTokenRegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        device_token = _register_device_token(request.user, serializer.validated_data)
    except IntegrityError:
        device_token = _register_device_token(request.user, serializer.validated_data)

    return Response(
        {
            "message": "Device token registered successfully.",
            "device_token": DeviceTokenSerializer(device_token).data,
        },
        status=200,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def unregister(request):
    serializer = DeviceTokenUnregisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    updated = DeviceToken.objects.filter(
        user=request.user,
        device_id=serializer.validated_data["device_id"],
        is_active=True,
    ).update(is_active=False)

    return Response(
        {
            "message": "Device token unregistered successfully.",
            "unregistered": bool(updated),
        }
    )
