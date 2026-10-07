import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Max, Q, Sum
from rest_framework import serializers
from rest_framework.exceptions import NotFound

from carts.models import Cart
from locations.models import Address
from notifications.tasks import send_store_owner_order_placed_notification
from orders.models import Order, OrderItem
from products.models import Product
from products.services import paginate_queryset
from stores.models import Store


User = get_user_model()


def _order_identifier_filter(identifier):
    lookup = Q(order_number=identifier)
    try:
        order_id = uuid.UUID(str(identifier))
    except ValueError:
        return lookup
    return lookup | Q(id=order_id)


def list_user_orders(user, filters):
    orders = (
        Order.objects.filter(user=user)
        .select_related(
            "store",
            "address",
            "address__city",
            "address__city__state",
        )
        .prefetch_related("items")
    )

    if filters.get("status"):
        orders = orders.filter(status=filters["status"])

    if filters.get("fullfillment_type"):
        orders = orders.filter(fullfillment_type=filters["fullfillment_type"])

    return orders.order_by("-created_at", "-id")


def list_user_store_orders(user, store_slug, filters):
    store = Store.objects.filter(slug=store_slug).first()
    if store is None:
        raise NotFound("Store not found.")

    orders = (
        Order.objects.filter(
            user=user,
            store=store,
        )
        .select_related(
            "store",
            "address",
            "address__city",
            "address__city__state",
        )
        .prefetch_related("items")
    )

    if filters.get("status"):
        orders = orders.filter(status=filters["status"])

    if filters.get("fullfillment_type"):
        orders = orders.filter(fullfillment_type=filters["fullfillment_type"])

    return orders.order_by("-created_at", "-id")


def list_store_orders(user, store_slug, filters):
    store = get_user_store(user, store_slug)
    orders = (
        Order.objects.filter(store=store)
        .select_related(
            "store",
            "user",
            "address",
            "address__city",
            "address__city__state",
        )
        .prefetch_related("items")
    )

    if filters.get("status"):
        orders = orders.filter(status=filters["status"])

    if filters.get("fullfillment_type"):
        orders = orders.filter(fullfillment_type=filters["fullfillment_type"])

    return orders.order_by("-created_at", "-id")


def list_store_customers(user, store_slug):
    store = get_user_store(user, store_slug)
    return (
        User.objects.filter(orders__store=store)
        .annotate(
            order_count=Count(
                "orders",
                filter=Q(orders__store=store),
                distinct=True,
            ),
            last_order_at=Max(
                "orders__created_at",
                filter=Q(orders__store=store),
            ),
            total_amount=Sum(
                "orders__total_amount",
                filter=Q(orders__store=store),
            ),
        )
        .order_by("-last_order_at", "full_name", "id")
    )


def get_order_for_response(order):
    return (
        Order.objects.select_related(
            "store",
            "user",
            "address",
            "address__city",
            "address__city__state",
        )
        .prefetch_related("items")
        .get(pk=order.pk)
    )


def get_user_store(user, store_slug):
    store = Store.objects.filter(owner=user, slug=store_slug).first()
    if store is None:
        raise NotFound("Store not found.")

    return store


def get_user_order(user, order_number):
    order = (
        Order.objects.filter(
            user=user,
        )
        .filter(_order_identifier_filter(order_number))
        .select_related(
            "store",
            "address",
            "address__city",
            "address__city__state",
        )
        .prefetch_related("items")
        .first()
    )
    if order is None:
        raise NotFound("Order not found.")
    return order


def get_store_order(user, store_slug, order_number):
    order = (
        Order.objects.filter(
            store__slug=store_slug,
            store__owner=user,
        )
        .filter(_order_identifier_filter(order_number))
        .select_related(
            "store",
            "user",
            "address",
            "address__city",
            "address__city__state",
        )
        .prefetch_related("items")
        .first()
    )
    if order is None:
        raise NotFound("Order not found.")
    return order


def create_order_from_cart(
    user,
    cart_id,
    address_id,
    fullfillment_type,
    payment_type=Order.PaymentType.CASH,
    customer_note="",
    add_with_existing=False,
    delivery_fee=0,
):
    cart = (
        Cart.objects.filter(
            id=cart_id,
            user=user,
            is_active=True,
        )
        .select_related("store")
        .prefetch_related("items__product", "items__variant")
        .first()
    )
    if cart is None:
        raise NotFound("Cart not found.")

    cart_items = list(cart.items.all())
    if not cart_items:
        raise serializers.ValidationError({"cart_id": "Cart is empty."})

    address = get_user_address(user, address_id)

    order = None
    if add_with_existing:
        order = get_existing_addable_order(user, cart.store)

    if order is None:
        order = create_cart_order(
            user,
            cart.store,
            address,
            fullfillment_type,
            payment_type,
            delivery_fee,
            customer_note,
        )
    else:
        update_existing_order_checkout_fields(
            order,
            address,
            fullfillment_type,
            payment_type,
            delivery_fee,
            customer_note,
        )

    for cart_item in cart_items:
        add_cart_item_to_order(
            order,
            cart_item,
            merge_with_existing=add_with_existing,
        )

    recalculate_order_totals(order)

    cart.is_active = False
    cart.save(update_fields=["is_active", "updated_at"])

    order_id = order.id
    transaction.on_commit(
        lambda: send_store_owner_order_placed_notification.delay(str(order_id))
    )

    return order


def update_existing_order_checkout_fields(
    order,
    address,
    fullfillment_type,
    payment_type=Order.PaymentType.CASH,
    delivery_fee=0,
    customer_note="",
):
    order.address = address
    order.fullfillment_type = fullfillment_type
    order.payment_type = payment_type
    order.delivery_fee = delivery_fee
    order.customer_note = customer_note or ""
    return order


def add_cart_item_to_order(order, cart_item, merge_with_existing=False):
    order_item = build_order_item_from_cart_item(order, cart_item)

    if merge_with_existing:
        existing_item = get_matching_order_item(order, order_item)
        if existing_item is not None:
            existing_item.quantity += order_item.quantity
            existing_item.line_total = (
                existing_item.unit_price
                * existing_item.quantity
            )
            save_order_item(existing_item)
            return existing_item

    save_order_item(order_item)
    return order_item


def get_matching_order_item(order, order_item):
    queryset = OrderItem.objects.filter(
        order=order,
        product=order_item.product,
        selection_type=order_item.selection_type,
    )

    if order_item.variant_id:
        return queryset.filter(variant=order_item.variant).first()

    return queryset.filter(
        variant__isnull=True,
        measurement_value=order_item.measurement_value,
        unit=order_item.unit,
        pack_count=order_item.pack_count,
    ).first()


def get_existing_addable_order(user, store):
    return (
        Order.objects.filter(
            user=user,
            store=store,
            status__in=(
                Order.Status.PLACED,
                Order.Status.READY,
            ),
        )
        .order_by("-created_at", "-id")
        .first()
    )


def create_cart_order(
    user,
    store,
    address,
    fullfillment_type,
    payment_type=Order.PaymentType.CASH,
    delivery_fee=0,
    customer_note="",
):
    order = Order(
        user=user,
        store=store,
        address=address,
        fullfillment_type=fullfillment_type,
        payment_type=payment_type,
        customer_note=customer_note or "",
        subtotal=0,
        delivery_fee=delivery_fee,
        discount_amount=0,
        total_amount=delivery_fee,
    )
    save_order(order)
    return order


def update_order(user, order_number, data):
    order = get_user_order(user, order_number)

    if "address_id" in data:
        order.address = get_user_address(user, data["address_id"])

    if "customer_note" in data:
        order.customer_note = data["customer_note"]

    if "status" in data:
        order.status = data["status"]
        mark_order_items_ready_for_final_status(order)

    if "fullfillment_type" in data:
        order.fullfillment_type = data["fullfillment_type"]

    if "payment_type" in data:
        order.payment_type = data["payment_type"]

    if "delivery_fee" in data:
        order.delivery_fee = data["delivery_fee"]
        order.total_amount = order.calculate_total()

    save_order(order)
    return order


def get_user_address(user, address_id):
    if address_id is None:
        return None

    address = Address.objects.filter(
        id=address_id,
        user=user,
    ).first()
    if address is None:
        raise serializers.ValidationError({"address_id": "Address not found."})
    return address


def update_store_order(user, store_slug, order_number, data):
    order = get_store_order(user, store_slug, order_number)

    if "customer_note" in data:
        order.customer_note = data["customer_note"]

    if "status" in data:
        order.status = data["status"]
        mark_order_items_ready_for_final_status(order)

    if "fullfillment_type" in data:
        order.fullfillment_type = data["fullfillment_type"]

    if "payment_type" in data:
        order.payment_type = data["payment_type"]

    if "delivery_fee" in data:
        order.delivery_fee = data["delivery_fee"]
        order.total_amount = order.calculate_total()

    if "discount_amount" in data:
        order.discount_amount = data["discount_amount"]
        order.total_amount = order.calculate_total()

    if "cancellation_reason" in data:
        order.cancellation_reason = data["cancellation_reason"]

    save_order(order)
    return order


def mark_order_items_ready_for_final_status(order):
    if order.status not in (
        Order.Status.READY,
        Order.Status.COMPLETED,
    ):
        return

    order.items.filter(is_ready=False).update(is_ready=True)


def cancel_order(user, order_number, cancellation_reason=""):
    order = get_user_order(user, order_number)
    if order.status in (
        Order.Status.CANCELLED,
        Order.Status.COMPLETED,
        Order.Status.REJECTED,
    ):
        raise serializers.ValidationError(
            {"status": "This order cannot be cancelled."}
        )

    order.status = Order.Status.CANCELLED
    order.cancellation_reason = cancellation_reason or ""
    save_order(order)
    return order


def update_order_item(user, item_id, data):
    item = get_accessible_order_item(user, item_id)

    if "quantity" in data:
        item.quantity = data["quantity"]
        item.line_total = item.unit_price * item.quantity

    if "is_not_available" in data:
        item.is_not_available = data["is_not_available"]

    if "is_ready" in data:
        item.is_ready = data["is_ready"]

    save_order_item(item)
    mark_order_ready_for_single_ready_item(item)
    recalculate_order_totals(item.order)
    return item.order


def mark_order_ready_for_single_ready_item(item):
    if not item.is_ready:
        return

    order = item.order
    if order.items.count() != 1:
        return

    order.status = Order.Status.READY


def delete_order_item(user, item_id):
    item = get_accessible_order_item(user, item_id)

    order = item.order
    if order.items.count() <= 1:
        raise serializers.ValidationError(
            {"items": "Order must have at least one item."}
        )

    item.delete()
    recalculate_order_totals(order)
    return order


def build_order_item_from_cart_item(order, cart_item):
    product = cart_item.product
    variant = cart_item.variant
    matching_variant = None

    if variant is None:
        matching_variant = cart_item.matching_custom_variant

    unit_price = cart_item.unit_price
    line_total = unit_price * cart_item.quantity

    return OrderItem(
        order=order,
        product=product,
        variant=variant,
        selection_type=(
            OrderItem.SelectionType.VARIANT
            if variant is not None
            else OrderItem.SelectionType.CUSTOM
        ),
        product_public_id=product.public_id,
        product_name=product.name,
        variant_name=get_variant_name(cart_item, matching_variant),
        measurement_type=product.measurement_type,
        measurement_value=get_measurement_value(cart_item, matching_variant),
        unit=get_unit(cart_item, matching_variant),
        pack_count=get_pack_count(cart_item, matching_variant),
        quantity=cart_item.quantity,
        unit_price=unit_price,
        mrp=get_mrp(cart_item, matching_variant),
        line_total=line_total,
    )


def get_variant_name(cart_item, matching_variant):
    if cart_item.variant_id:
        return cart_item.variant.name
    if matching_variant is not None:
        return matching_variant.name
    return cart_item.display_custom_measurement


def get_measurement_value(cart_item, matching_variant):
    if cart_item.variant_id:
        return cart_item.variant.value
    if matching_variant is not None:
        return matching_variant.value
    return cart_item.custom_value


def get_unit(cart_item, matching_variant):
    if cart_item.variant_id:
        return cart_item.variant.unit
    if matching_variant is not None:
        return matching_variant.unit

    return {
        Product.MeasurementType.NONE: "pack",
        Product.MeasurementType.COUNT: "piece",
        Product.MeasurementType.WEIGHT: "g",
        Product.MeasurementType.VOLUME: "ml",
    }.get(cart_item.product.measurement_type, "")


def get_pack_count(cart_item, matching_variant):
    if cart_item.variant_id:
        return cart_item.variant.pack_count
    if matching_variant is not None:
        return matching_variant.pack_count
    return 1


def get_mrp(cart_item, matching_variant):
    if cart_item.variant_id:
        return cart_item.variant.mrp
    if matching_variant is not None:
        return matching_variant.mrp
    return None


def get_accessible_order_item(user, item_id):
    item = (
        OrderItem.objects.select_related(
            "order",
            "order__store",
        )
        .filter(
            id=item_id,
        )
        .filter(Q(order__user=user) | Q(order__store__owner=user))
        .first()
    )
    if item is None:
        raise NotFound("Order item not found.")
    return item


def recalculate_order_totals(order):
    subtotal = sum(
        item.line_total
        for item in order.items.all()
    )
    order.subtotal = subtotal
    order.total_amount = order.calculate_total()
    save_order(order)
    return order


def save_order(order):
    try:
        order.full_clean()
        order.save()
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.message_dict) from exc
    return order


def save_order_item(item):
    try:
        item.full_clean()
        item.save()
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.message_dict) from exc
    return item
