from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from orders import services
from orders.serializers import (
    OrderCancelSerializer,
    OrderCreateFromCartSerializer,
    OrderItemUpdateSerializer,
    OrderListQuerySerializer,
    OrderSerializer,
    StoreCustomerListQuerySerializer,
    StoreCustomerSerializer,
    StoreOrderSerializer,
    StoreOrderUpdateSerializer,
    OrderUpdateSerializer,
)


def _get_order_response(order, request, status=None):
    order = services.get_order_for_response(order)
    return Response(
        {"order": OrderSerializer(order, context={"request": request}).data},
        status=status,
    )


def _get_store_order_response(order, request, status=None):
    order = services.get_order_for_response(order)
    return Response(
        {"order": StoreOrderSerializer(order, context={"request": request}).data},
        status=status,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_store_customer_list(request, store_slug):
    serializer = StoreCustomerListQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    filters = serializer.validated_data

    customers = services.list_store_customers(request.user, store_slug)
    page, count, pagination = services.paginate_queryset(
        customers,
        request,
        filters["page_size"],
    )
    return Response(
        {
            "count": count,
            "pagination": pagination,
            "results": StoreCustomerSerializer(page, many=True).data,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_store_order_list(request, store_slug):
    serializer = OrderListQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    filters = serializer.validated_data

    orders = services.list_store_orders(request.user, store_slug, filters)
    page, count, pagination = services.paginate_queryset(
        orders,
        request,
        filters["page_size"],
    )
    return Response(
        {
            "count": count,
            "pagination": pagination,
            "results": StoreOrderSerializer(
                page,
                many=True,
                context={"request": request},
            ).data,
        }
    )


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def my_store_order_detail(request, store_slug, order_number):
    if request.method == "GET":
        order = services.get_store_order(request.user, store_slug, order_number)
        return _get_store_order_response(order, request)

    serializer = StoreOrderUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    order = services.update_store_order(
        request.user,
        store_slug,
        order_number,
        serializer.validated_data,
    )
    return _get_store_order_response(order, request)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def order_list(request):
    serializer = OrderListQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    filters = serializer.validated_data

    orders = services.list_user_orders(request.user, filters)
    page, count, pagination = services.paginate_queryset(
        orders,
        request,
        filters["page_size"],
    )
    return Response(
        {
            "count": count,
            "pagination": pagination,
            "results": OrderSerializer(
                page,
                many=True,
                context={"request": request},
            ).data,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def store_user_order_list(request, store_slug):
    serializer = OrderListQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    filters = serializer.validated_data

    orders = services.list_user_store_orders(request.user, store_slug, filters)
    page, count, pagination = services.paginate_queryset(
        orders,
        request,
        filters["page_size"],
    )
    return Response(
        {
            "count": count,
            "pagination": pagination,
            "results": OrderSerializer(
                page,
                many=True,
                context={"request": request},
            ).data,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def create_order_from_cart(request):
    serializer = OrderCreateFromCartSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    order = services.create_order_from_cart(
        user=request.user,
        cart_id=serializer.validated_data["cart_id"],
        address_id=serializer.validated_data.get("address_id"),
        fullfillment_type=serializer.validated_data["fullfillment_type"],
        payment_type=serializer.validated_data["payment_type"],
        customer_note=serializer.validated_data.get("customer_note", ""),
        add_with_existing=serializer.validated_data["add_with_existing"],
        delivery_fee=serializer.validated_data["delivery_fee"],
    )
    return _get_order_response(order, request, status=201)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def order_detail(request, order_number):
    if request.method == "GET":
        order = services.get_user_order(request.user, order_number)
        return _get_order_response(order, request)

    serializer = OrderUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    order = services.update_order(
        request.user,
        order_number,
        serializer.validated_data,
    )
    return _get_order_response(order, request)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def cancel_order(request, order_number):
    serializer = OrderCancelSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    order = services.cancel_order(
        request.user,
        order_number,
        serializer.validated_data.get("cancellation_reason", ""),
    )
    return _get_order_response(order, request)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def order_item_detail(request, item_id):
    if request.method == "DELETE":
        order = services.delete_order_item(request.user, item_id)
        return _get_order_response(order, request)

    serializer = OrderItemUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    order = services.update_order_item(
        request.user,
        item_id,
        serializer.validated_data,
    )
    return _get_order_response(order, request)
