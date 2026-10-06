from django.contrib import admin

from notifications.models import DeviceToken


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "device_id",
        "platform",
        "is_active",
        "failure_count",
        "last_seen_at",
        "updated_at",
    )
    list_filter = ("platform", "is_active", "created_at", "updated_at")
    search_fields = (
        "user__phone",
        "user__email",
        "user__full_name",
        "device_id",
        "token",
        "browser",
        "os",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-updated_at",)
    list_select_related = ("user",)
