from django.urls import path

from locations import views


app_name = "locations"

urlpatterns = [
    path("locations/cities/", views.city_list, name="city-list"),
    path("users/me/addresses/", views.user_address_list, name="user-address-list"),
    path(
        "users/me/addresses/<uuid:address_id>/",
        views.user_address_detail,
        name="user-address-detail",
    ),
]
