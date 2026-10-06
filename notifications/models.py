import uuid

from django.conf import settings
from django.db import models

from core.models import TimestampedModel


class DeviceToken(TimestampedModel):
    class Platform(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"
        WEB = "web", "Web"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # ------------------------------------------------------------
    # USER
    # ------------------------------------------------------------

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_tokens",
        null=True,
        blank=True,
    )

    # ------------------------------------------------------------
    # DEVICE
    # ------------------------------------------------------------

    device_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text=(
            "Stable client-generated identifier for this browser/device "
            "installation."
        ),
    )

    platform = models.CharField(
        max_length=20,
        choices=Platform.choices,
        db_index=True,
    )

    # ------------------------------------------------------------
    # PUSH TOKEN
    # ------------------------------------------------------------

    token = models.TextField(
        unique=True,
        help_text="Firebase Cloud Messaging registration token.",
    )

    # ------------------------------------------------------------
    # DEVICE METADATA
    # ------------------------------------------------------------

    device_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional human-readable device name.",
    )

    app_version = models.CharField(
        max_length=50,
        blank=True,
    )

    browser = models.CharField(
        max_length=100,
        blank=True,
    )

    os = models.CharField(
        max_length=100,
        blank=True,
    )

    # ------------------------------------------------------------
    # STATUS
    # ------------------------------------------------------------

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    failure_count = models.PositiveSmallIntegerField(
        default=0,
        help_text="Consecutive push delivery failures.",
    )

    last_seen_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this device/token was confirmed by the client.",
    )

    last_notification_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-updated_at"]

        indexes = [
            models.Index(
                fields=["user", "is_active"],
                name="device_user_active_idx",
            ),
            models.Index(
                fields=["device_id", "is_active"],
                name="device_id_active_idx",
            ),
            models.Index(
                fields=["platform", "is_active"],
                name="device_platform_active_idx",
            ),
        ]

    def __str__(self):
        user = self.user_id or "Anonymous"
        return f"{user} - {self.platform} - {self.token[:20]}..."
