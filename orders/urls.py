from django.urls import path

from orders import views


app_name = "orders"

urlpatterns = [
    path(
        "stores/my/<slug:store_slug>/orders/",
        views.my_store_order_list,
        name="my-store-order-list",
    ),
    path(
        "stores/my/<slug:store_slug>/customers/",
        views.my_store_customer_list,
        name="my-store-customer-list",
    ),
    path(
        "stores/my/<slug:store_slug>/orders/<str:order_number>/",
        views.my_store_order_detail,
        name="my-store-order-detail",
    ),
    path(
        "<slug:store_slug>/orders/",
        views.store_user_order_list,
        name="store-user-order-list",
    ),
    path(
        "orders/",
        views.order_list,
        name="order-list",
    ),
    path(
        "orders/from-cart/",
        views.create_order_from_cart,
        name="order-create-from-cart",
    ),
    path(
        "orders/<str:order_number>/",
        views.order_detail,
        name="order-detail",
    ),
    path(
        "orders/<str:order_number>/cancel/",
        views.cancel_order,
        name="order-cancel",
    ),
    path(
        "orders/items/<uuid:item_id>/",
        views.order_item_detail,
        name="order-item-detail",
    ),
]
