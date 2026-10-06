from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from carts import services
from carts.serializers import (
    CartItemAddSerializer,
    CartItemUpdateSerializer,
    CartSerializer,
)


def _get_cart_response(cart, request, status=None):
    cart = services.get_cart_for_response(cart)
    return Response(
        {"cart": CartSerializer(cart, context={"request": request}).data},
        status=status,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def active_cart_detail(request, store_slug):
    store = services.get_active_store(store_slug)
    cart = services.get_active_cart(request.user, store)
    if cart is None:
        return Response({"cart": None})

    return Response({"cart": CartSerializer(cart, context={"request": request}).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def add_cart_item(request, store_slug):
    print("Cart item add payload:", dict(request.data))
    serializer = CartItemAddSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    cart = services.add_item_to_cart(
        request.user,
        store_slug,
        serializer.validated_data,
    )
    return _get_cart_response(cart, request, status=201)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def cart_item_detail(request, item_id):
    if request.method == "DELETE":
        cart = services.delete_cart_item(request.user, item_id)
        return _get_cart_response(cart, request)

    print("Cart item update payload:", dict(request.data))
    serializer = CartItemUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    cart = services.update_cart_item(
        request.user,
        item_id,
        serializer.validated_data,
    )
    return _get_cart_response(cart, request)
