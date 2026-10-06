from django.urls import path

from core import views


app_name = "core"

urlpatterns = [
    path("health/", views.health, name="health"),
    path("ready/", views.readiness, name="readiness"),
    path(
        "notifications/send-device/",
        views.send_device_notification,
        name="send-device-notification",
    ),
]
