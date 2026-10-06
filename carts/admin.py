from django.contrib import admin

from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem

    extra = 0

    fields = (
        "product",
        "variant",
        "custom_value",
        "quantity",
        "unit_price",
        "display_measurement_admin",
        "total_price_admin",
        "created_at",
    )

    readonly_fields = (
        "unit_price",
        "display_measurement_admin",
        "total_price_admin",
        "created_at",
    )

    autocomplete_fields = (
        "product",
        "variant",
    )

    show_change_link = True

    @admin.display(description="Measurement")
    def display_measurement_admin(self, obj):
        if not obj:
            return "-"

        return obj.display_measurement

    @admin.display(description="Total")
    def total_price_admin(self, obj):
        if not obj:
            return "-"

        return f"₹{obj.total_price}"


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "user",
        "store",
        "item_count_admin",
        "total_units_admin",
        "subtotal_admin",
        "is_active",
        "updated_at",
    )

    list_filter = (
        "is_active",
        "store",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "user__email",
        "user__username",
        "store__name",
    )

    autocomplete_fields = (
        "user",
        "store",
    )

    readonly_fields = (
        "id",
        "item_count_admin",
        "total_units_admin",
        "subtotal_admin",
        "created_at",
        "updated_at",
    )

    ordering = (
        "-updated_at",
    )

    list_per_page = 50

    inlines = [
        CartItemInline,
    ]

    fieldsets = (
        (
            "Cart",
            {
                "fields": (
                    "id",
                    "user",
                    "store",
                    "is_active",
                )
            },
        ),
        (
            "Summary",
            {
                "fields": (
                    "item_count_admin",
                    "total_units_admin",
                    "subtotal_admin",
                )
            },
        ),
        (
            "System",
            {
                "classes": (
                    "collapse",
                ),
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "user",
                "store",
            )
            .prefetch_related(
                "items",
                "items__product",
                "items__variant",
            )
        )

    @admin.display(description="Items")
    def item_count_admin(self, obj):
        return obj.item_count

    @admin.display(description="Units")
    def total_units_admin(self, obj):
        return obj.total_units

    @admin.display(description="Subtotal")
    def subtotal_admin(self, obj):
        return f"₹{obj.subtotal}"


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):

    list_display = (
        "product",
        "cart_user",
        "store",
        "display_measurement_admin",
        "quantity",
        "unit_price_admin",
        "total_price_admin",
        "created_at",
    )

    list_filter = (
        "cart__store",
        "product__measurement_type",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "product__name",
        "product__public_id",
        "cart__user__email",
        "cart__user__username",
        "cart__store__name",
    )

    autocomplete_fields = (
        "cart",
        "product",
        "variant",
    )

    readonly_fields = (
        "id",
        "unit_price",
        "display_measurement_admin",
        "total_price_admin",
        "total_measurement_admin",
        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )

    list_per_page = 50

    fieldsets = (
        (
            "Cart Item",
            {
                "fields": (
                    "id",
                    "cart",
                    "product",
                    "variant",
                    "custom_value",
                    "quantity",
                )
            },
        ),
        (
            "Pricing",
            {
                "fields": (
                    "unit_price",
                    "total_price_admin",
                )
            },
        ),
        (
            "Measurement",
            {
                "fields": (
                    "display_measurement_admin",
                    "total_measurement_admin",
                )
            },
        ),
        (
            "System",
            {
                "classes": (
                    "collapse",
                ),
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "cart",
                "cart__user",
                "cart__store",
                "product",
                "variant",
            )
        )

    @admin.display(description="User")
    def cart_user(self, obj):
        return obj.cart.user

    @admin.display(description="Store")
    def store(self, obj):
        return obj.cart.store

    @admin.display(description="Measurement")
    def display_measurement_admin(self, obj):
        return obj.display_measurement or "-"

    @admin.display(description="Unit Price")
    def unit_price_admin(self, obj):
        return f"₹{obj.unit_price}"

    @admin.display(description="Total")
    def total_price_admin(self, obj):
        return f"₹{obj.total_price}"

    @admin.display(description="Total Measurement")
    def total_measurement_admin(self, obj):
        value = obj.total_measurement_value

        if value is None:
            return "-"

        measurement_type = (
            obj.product.measurement_type
        )

        if (
            measurement_type
            == obj.product.MeasurementType.WEIGHT
        ):
            if value >= 1000:
                return (
                    f"{obj._format_thousand(value)} kg"
                )

            return f"{value} g"

        if (
            measurement_type
            == obj.product.MeasurementType.VOLUME
        ):
            if value >= 1000:
                return (
                    f"{obj._format_thousand(value)} L"
                )

            return f"{value} ml"

        if (
            measurement_type
            == obj.product.MeasurementType.COUNT
        ):
            if value == 1:
                return "1 Piece"

            return f"{value} Pieces"

        return "-"