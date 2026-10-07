import uuid

from django.contrib.auth import get_user_model
from rest_framework import serializers

from locations.serializers import AddressSerializer
from orders.models import Order, OrderItem


User = get_user_model()


class OrderItemSerializer(serializers.ModelSerializer):
    total_measurement_value = serializers.IntegerField(read_only=True, allow_null=True)
    discount_amount = serializers.IntegerField(read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product",
            "variant",
            "selection_type",
            "product_public_id",
            "product_name",
            "variant_name",
            "measurement_type",
            "measurement_value",
            "unit",
            "pack_count",
            "quantity",
            "unit_price",
            "mrp",
            "line_total",
            "is_not_available",
            "is_ready",
            "total_measurement_value",
            "discount_amount",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    store = serializers.SerializerMethodField()
    address = AddressSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    total_units = serializers.IntegerField(read_only=True)
    not_available_amount = serializers.IntegerField(read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "order_number",
            "store",
            "address",
            "status",
            "fullfillment_type",
            "payment_type",
            "subtotal",
            "delivery_fee",
            "discount_amount",
            "not_available_amount",
            "total_amount",
            "customer_note",
            "cancellation_reason",
            "item_count",
            "total_units",
            "items",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "order_number",
            "store",
            "address",
            "status",
            "fullfillment_type",
            "payment_type",
            "subtotal",
            "delivery_fee",
            "discount_amount",
            "not_available_amount",
            "total_amount",
            "cancellation_reason",
            "item_count",
            "total_units",
            "items",
            "created_at",
            "updated_at",
        )

    def get_store(self, obj):
        return {
            "id": obj.store_id,
            "name": obj.store.name,
            "slug": obj.store.slug,
        }


class StoreOrderSerializer(OrderSerializer):
    customer = serializers.SerializerMethodField()

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields[:3] + (
            "customer",
        ) + OrderSerializer.Meta.fields[3:]
        read_only_fields = fields

    def get_customer(self, obj):
        return {
            "id": obj.user_id,
            "full_name": obj.user.full_name,
            "phone": obj.user.phone,
            "email": obj.user.email,
        }


class StoreCustomerSerializer(serializers.ModelSerializer):
    order_count = serializers.IntegerField(read_only=True)
    last_order_at = serializers.DateTimeField(read_only=True)
    total_amount = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "full_name",
            "phone",
            "email",
            "order_count",
            "last_order_at",
            "total_amount",
        )
        read_only_fields = fields


class OrderCreateFromCartSerializer(serializers.Serializer):
    cart_id = serializers.UUIDField()
    address_id = serializers.UUIDField(required=False, allow_null=True)
    fullfillment_type = serializers.ChoiceField(
        choices=Order.FullfillmentType.choices,
    )
    payment_type = serializers.ChoiceField(
        required=False,
        choices=Order.PaymentType.choices,
        default=Order.PaymentType.CASH,
    )
    delivery_fee = serializers.IntegerField(required=False, default=0, min_value=0)
    add_with_existing = serializers.BooleanField(default=False)
    customer_note = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
    )


class OrderListQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        required=False,
        choices=Order.Status.choices,
    )
    fullfillment_type = serializers.ChoiceField(
        required=False,
        choices=Order.FullfillmentType.choices,
    )
    payment_type = serializers.ChoiceField(
        required=False,
        choices=Order.PaymentType.choices,
    )
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(
        required=False,
        default=20,
        min_value=1,
        max_value=100,
    )


class StoreCustomerListQuerySerializer(serializers.Serializer):
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(
        required=False,
        default=20,
        min_value=1,
        max_value=100,
    )


class OrderUpdateSerializer(serializers.Serializer):
    address_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    customer_note = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
    )
    status = serializers.ChoiceField(
        required=False,
        choices=Order.Status.choices,
    )
    fullfillment_type = serializers.ChoiceField(
        required=False,
        choices=Order.FullfillmentType.choices,
    )
    payment_type = serializers.ChoiceField(
        required=False,
        choices=Order.PaymentType.choices,
    )
    delivery_fee = serializers.IntegerField(
        required=False,
        min_value=0,
    )

    def validate_address_id(self, value):
        if value in ("", None):
            return None

        try:
            return uuid.UUID(str(value))
        except ValueError as exc:
            raise serializers.ValidationError("Enter a valid UUID.") from exc

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide at least one field to update.")
        return attrs


class StoreOrderUpdateSerializer(serializers.Serializer):
    customer_note = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
    )
    status = serializers.ChoiceField(
        required=False,
        choices=Order.Status.choices,
    )
    fullfillment_type = serializers.ChoiceField(
        required=False,
        choices=Order.FullfillmentType.choices,
    )
    delivery_fee = serializers.IntegerField(
        required=False,
        min_value=0,
    )
    discount_amount = serializers.IntegerField(
        required=False,
        min_value=0,
    )
    cancellation_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide at least one field to update.")
        return attrs


class OrderCancelSerializer(serializers.Serializer):
    cancellation_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
    )


class OrderItemUpdateSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(required=False, min_value=1)
    is_not_available = serializers.BooleanField(required=False)
    is_ready = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide at least one field to update.")
        return attrs
