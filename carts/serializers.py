from django.core.files.storage import default_storage
from rest_framework import serializers

from carts.models import Cart, CartItem
from uploads.models import Upload


class CartItemSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField(source="product.id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_image_url = serializers.SerializerMethodField()
    measurement_type = serializers.CharField(
        source="product.measurement_type",
        read_only=True,
    )
    quantity_step = serializers.IntegerField(
        source="product.quantity_step",
        read_only=True,
        allow_null=True,
    )
    unit = serializers.SerializerMethodField()
    variant_id = serializers.SerializerMethodField()
    display_measurement = serializers.CharField(read_only=True)
    total_price = serializers.IntegerField(read_only=True)
    total_measurement_value = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = CartItem
        fields = (
            "id",
            "product_id",
            "product_name",
            "product_image_url",
            "measurement_type",
            "quantity_step",
            "unit",
            "variant_id",
            "custom_value",
            "display_measurement",
            "quantity",
            "unit_price",
            "total_price",
            "total_measurement_value",
            "created_at",
            "updated_at",
        )

    def get_variant_id(self, obj):
        return obj.variant_id

    def get_product_image_url(self, obj):
        ready_uploads = getattr(obj.product, "ready_uploads", None)
        upload = (
            ready_uploads[0]
            if ready_uploads
            else obj.product.uploads.filter(status=Upload.Status.READY).first()
        )
        if upload is None:
            return None

        url = default_storage.url(upload.object_key)
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request and url.startswith("/") else url

    def get_unit(self, obj):
        if obj.variant_id:
            return obj.variant.unit

        return {
            "none": "pack",
            "count": "piece",
            "weight": "g",
            "volume": "ml",
        }.get(obj.product.measurement_type)


class CartSerializer(serializers.ModelSerializer):
    store = serializers.SerializerMethodField()
    items = CartItemSerializer(many=True, read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    total_units = serializers.IntegerField(read_only=True)
    subtotal = serializers.IntegerField(read_only=True)

    class Meta:
        model = Cart
        fields = (
            "id",
            "store",
            "is_active",
            "item_count",
            "total_units",
            "subtotal",
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


class CartItemAddSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    variant_id = serializers.UUIDField(required=False, allow_null=True)
    custom_value = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    quantity = serializers.IntegerField(default=1, min_value=1)

    def validate(self, attrs):
        variant_id = attrs.get("variant_id")
        custom_value = attrs.get("custom_value")

        if bool(variant_id) == (custom_value is not None):
            raise serializers.ValidationError(
                "Provide exactly one of variant_id or custom_value."
            )

        return attrs


class CartItemUpdateSerializer(serializers.Serializer):
    custom_value = serializers.IntegerField(required=False, min_value=1)
    quantity = serializers.IntegerField(required=False, min_value=1)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "Provide at least one of custom_value or quantity."
            )
        return attrs
