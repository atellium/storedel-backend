from django.urls import path

from stores import views


app_name = "stores"

urlpatterns = [
    path("stores/", views.store_list, name="store-list"),
    path("stores/nearby/", views.nearby_store_list, name="nearby-store-list"),
    path("stores/saved/", views.saved_store_list, name="saved-store-list"),
    path(
        "stores/my/<slug:store_slug>/orders/page/",
        views.my_store_order_page,
        name="my-store-order-page",
    ),
    path(
        "stores/my/",
        views.my_business_list,
        name="my-business-list",
    ),
    path(
        "stores/my/<slug:store_slug>/settings/",
        views.my_store_settings_update,
        name="my-store-settings-update",
    ),
    path(
        "stores/my/<slug:store_slug>/",
        views.my_business_detail,
        name="my-business-detail",
    ),
    path(
        "stores/<slug:store_slug>/save/",
        views.saved_store_detail,
        name="saved-store-detail",
    ),
    path(
        "stores/<slug:store_slug>/settings/",
        views.store_settings_detail,
        name="store-settings-detail",
    ),
    path("stores/<str:store_slug>/", views.store_detail, name="store-detail"),
]
