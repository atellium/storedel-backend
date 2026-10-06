from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import Prefetch
from rest_framework import serializers
from rest_framework.exceptions import NotFound

from carts.models import Cart, CartItem
from products.models import Product, ProductVariant
from stores.models import Store
from uploads.models import Upload


READY_PRODUCT_UPLOADS_PREFETCH = Prefetch(
    "items__product__uploads",
    queryset=Upload.objects.filter(status=Upload.Status.READY).order_by("created_at"),
    to_attr="ready_uploads",
)


def get_active_store(store_slug):
    store = Store.objects.filter(slug=store_slug, is_active=True).first()
    if store is None:
        raise NotFound("Store not found.")
    return store


def get_active_cart(user, store):
    return (
        Cart.objects.filter(
            user=user,
            store=store,
            is_active=True,
        )
        .select_related("store")
        .prefetch_related("items__product", "items__variant", READY_PRODUCT_UPLOADS_PREFETCH)
        .first()
    )


def get_cart_for_response(cart):
    return (
        Cart.objects.select_related("store")
        .prefetch_related("items__product", "items__variant", READY_PRODUCT_UPLOADS_PREFETCH)
        .get(pk=cart.pk)
    )


def add_item_to_cart(user, store_slug, data):
    store = get_active_store(store_slug)
    product = get_store_product(store, data["product_id"])
    variant = get_product_variant(product, data.get("variant_id"))
    custom_value = data.get("custom_value")

    if variant is not None and product.allow_custom_quantity:
        custom_value = variant.value
        variant = None

    cart, _ = Cart.objects.get_or_create(
        user=user,
        store=store,
        is_active=True,
    )

    item = get_existing_cart_item(cart, product, variant)

    if item is None:
        item = CartItem(
            cart=cart,
            product=product,
            variant=variant,
            custom_value=custom_value,
            quantity=data["quantity"],
        )
        try:
            save_cart_item(item)
        except IntegrityError:
            item = get_existing_cart_item(cart, product, variant, for_update=True)
            update_existing_cart_item(item, custom_value, data["quantity"])
    else:
        update_existing_cart_item(item, custom_value, data["quantity"])

    return cart


def update_cart_item(user, item_id, data):
    item = get_active_user_cart_item(user, item_id)

    if "quantity" in data:
        item.quantity = data["quantity"]

    if "custom_value" in data:
        if item.variant_id or not item.product.allow_custom_quantity:
            raise serializers.ValidationError(
                {
                    "custom_value": (
                        "Custom value can only be updated for custom quantity items."
                    )
                }
            )
        item.custom_value = data["custom_value"]

    save_cart_item(item)
    return item.cart


def delete_cart_item(user, item_id):
    item = get_active_user_cart_item(user, item_id)
    cart = item.cart
    item.delete()
    return cart


def get_store_product(store, product_id):
    try:
        return Product.objects.get(
            id=product_id,
            store=store,
        )
    except Product.DoesNotExist as exc:
        raise serializers.ValidationError(
            {"product_id": "Product not found in this store."}
        ) from exc


def get_product_variant(product, variant_id):
    if not variant_id:
        return None

    try:
        return ProductVariant.objects.get(
            id=variant_id,
            product=product,
        )
    except ProductVariant.DoesNotExist as exc:
        raise serializers.ValidationError(
            {"variant_id": "Variant not found for this product."}
        ) from exc


def get_existing_cart_item(cart, product, variant, for_update=False):
    queryset = CartItem.objects
    if for_update:
        queryset = queryset.select_for_update()

    if variant is not None:
        return queryset.filter(cart=cart, variant=variant).first()

    return (
        queryset.filter(
            cart=cart,
            product=product,
            variant__isnull=True,
        )
        .order_by("created_at")
        .first()
    )


def update_existing_cart_item(item, custom_value, quantity):
    if item.variant_id is None:
        item.custom_value = custom_value

    return increment_cart_item(item, quantity)


def increment_cart_item(item, quantity):
    item.quantity += quantity
    save_cart_item(item)
    return item


def get_active_user_cart_item(user, item_id):
    item = (
        CartItem.objects.select_related("cart")
        .filter(
            id=item_id,
            cart__user=user,
            cart__is_active=True,
        )
        .first()
    )
    if item is None:
        raise NotFound("Cart item not found.")
    return item


def save_cart_item(item):
    try:
        item.save()
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.message_dict) from exc
    return item
