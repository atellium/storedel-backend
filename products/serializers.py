import json

from django.core.files.storage import default_storage
from rest_framework import serializers

from carts.models import CartItem
from products.models import Product, ProductCategory, ProductVariant
from uploads.serializers import UploadSerializer


class ProductCategoryImageUrlMixin(serializers.Serializer):
    image_url = serializers.SerializerMethodField()

    def get_image_url(self, obj):
        if not obj.image:
            return None
        url = default_storage.url(obj.image.name)
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request and url.startswith("/") else url


class ProductCategorySerializer(ProductCategoryImageUrlMixin, serializers.ModelSerializer):
    parent_id = serializers.IntegerField(
        source="parent.id",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = ProductCategory
        fields = (
            "id",
            "name",
            "label",
            "display_name",
            "slug",
            "aliases",
            "image_url",
            "parent_id",
            "sort_order",
            "is_active",
            "is_featured",
            "is_searchable",
            "created_at",
            "updated_at",
        )


class ProductCategoryFlatSerializer(ProductCategoryImageUrlMixin, serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = (
            "id",
            "name",
            "slug",
            "aliases",
            "image_url",
            "sort_order",
        )


class ProductVariantListSerializer(serializers.Serializer):
    cart_count = serializers.SerializerMethodField()
    id = serializers.UUIDField()
    name = serializers.CharField()
    value = serializers.IntegerField(allow_null=True)
    unit = serializers.CharField()
    display_measurement = serializers.CharField()
    pack_count = serializers.IntegerField()
    total_measurement_value = serializers.IntegerField(allow_null=True)
    price = serializers.IntegerField()
    mrp = serializers.IntegerField(allow_null=True)
    discount_amount = serializers.IntegerField()
    discount_percentage = serializers.IntegerField()
    is_default = serializers.BooleanField()
    is_active = serializers.BooleanField()
    sort_order = serializers.IntegerField()

    def get_cart_count(self, obj):
        request = self.context.get("request")
        if (
            request is None
            or not request.user
            or not request.user.is_authenticated
        ):
            return 0

        return (
            CartItem.objects.filter(
                cart__user=request.user,
                cart__is_active=True,
                variant=obj,
            )
            .values_list("quantity", flat=True)
            .first()
            or 0
        )


class OwnerProductVariantSerializer(ProductVariantListSerializer):
    cost_price = serializers.IntegerField(allow_null=True)


class ProductVariantWriteSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False)
    value = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
    )
    unit = serializers.ChoiceField(
        required=False,
        choices=ProductVariant.Unit.choices,
    )
    pack_count = serializers.IntegerField(required=False, min_value=1)
    price = serializers.IntegerField(required=False, min_value=0)
    mrp = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    cost_price = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
    )
    is_default = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)
    sort_order = serializers.IntegerField(required=False, min_value=0)


class ProductStoreSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.SlugField()


class ProductListSerializer(serializers.ModelSerializer):
    store = ProductStoreSerializer(read_only=True)
    categories = ProductCategoryFlatSerializer(many=True, read_only=True)
    uploads = UploadSerializer(many=True, read_only=True)
    variants = ProductVariantListSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "public_id",
            "store",
            "name",
            "slug",
            "short_description",
            "categories",
            "uploads",
            "brand",
            "measurement_type",
            "allow_custom_quantity",
            "base_quantity",
            "base_price",
            "minimum_quantity",
            "quantity_step",
            "specifications",
            "is_active",
            "is_featured",
            "sort_order",
            "variants",
            "created_at",
            "updated_at",
        )


class ProductWriteSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, max_length=200)
    short_description = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=300,
    )
    category_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
    )
    upload_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )
    brand = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=120,
    )
    measurement_type = serializers.ChoiceField(
        required=False,
        choices=Product.MeasurementType.choices,
    )
    allow_custom_quantity = serializers.BooleanField(required=False)
    base_quantity = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
    )
    base_price = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
    )
    minimum_quantity = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
    )
    quantity_step = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
    )
    specifications = serializers.JSONField(required=False)
    is_active = serializers.BooleanField(required=False)
    is_featured = serializers.BooleanField(required=False)
    sort_order = serializers.IntegerField(required=False, min_value=0)

    def validate(self, attrs):
        if self.context.get("is_create") and not attrs.get("name"):
            raise serializers.ValidationError({"name": "This field is required."})

        for field in ("category_ids", "upload_ids"):
            values = attrs.get(field)
            if values is not None and len(values) != len(set(values)):
                raise serializers.ValidationError(
                    {field: "Values must be unique."}
                )

        return attrs


class StoreProductListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(
        required=False,
        max_length=180,
        trim_whitespace=True,
        allow_blank=False,
    )
    category = serializers.SlugField(required=False, max_length=150)
    is_custom_quantity = serializers.BooleanField(required=False)
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(
        required=False,
        default=20,
        min_value=1,
        max_value=100,
    )


class ProductCategoryListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(
        required=False,
        max_length=180,
        trim_whitespace=True,
        allow_blank=False,
    )
    parent_slug = serializers.SlugField(required=False, max_length=150)
    root_only = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)
    is_featured = serializers.BooleanField(required=False)
    is_searchable = serializers.BooleanField(required=False)
    ordering = serializers.ChoiceField(
        required=False,
        default="sort_order",
        choices=(
            "sort_order",
            "-sort_order",
            "name",
            "-name",
            "label",
            "-label",
            "created_at",
            "-created_at",
            "updated_at",
            "-updated_at",
        ),
    )
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(
        required=False,
        default=20,
        min_value=1,
        max_value=100,
    )


class ProductCategoryImportSerializer(serializers.Serializer):
    parent_id = serializers.IntegerField()
    file = serializers.FileField()

    def validate_parent_id(self, value):
        if value is None:
            return None
        try:
            return ProductCategory.objects.get(pk=value)
        except ProductCategory.DoesNotExist as exc:
            raise serializers.ValidationError("Parent category not found.") from exc

    def validate_file(self, value):
        if not value.name.lower().endswith(".json"):
            raise serializers.ValidationError("Upload a JSON file.")

        try:
            payload = json.loads(value.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise serializers.ValidationError("Upload a valid JSON file.") from exc

        categories = payload
        if not isinstance(categories, list):
            raise serializers.ValidationError("JSON must be a flat list.")
        if not categories:
            raise serializers.ValidationError("JSON file must include categories.")
        if any(not isinstance(category, dict) for category in categories):
            raise serializers.ValidationError("Each category must be an object.")
        if any("children" in category for category in categories):
            raise serializers.ValidationError("Nested children are not supported.")

        value.categories = categories
        return value
