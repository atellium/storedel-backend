from django.urls import path

from carts import views


app_name = "carts"

urlpatterns = [
    path(
        "stores/<slug:store_slug>/cart/",
        views.active_cart_detail,
        name="active-cart-detail",
    ),
    path(
        "stores/<slug:store_slug>/cart/items/",
        views.add_cart_item,
        name="cart-item-add",
    ),
    path(
        "cart/items/<uuid:item_id>/",
        views.cart_item_detail,
        name="cart-item-detail",
    ),
]
