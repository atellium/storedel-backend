from django.urls import path

from notifications import views

app_name = "notifications"

urlpatterns = [
    path("device-tokens/register/", views.register, name="device-token-register"),
    path(
        "device-tokens/unregister/",
        views.unregister,
        name="device-token-unregister",
    ),
]
