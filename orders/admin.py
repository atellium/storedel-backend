from django.contrib import admin

from orders.models import Order, OrderItem


# ============================================================
# Order Item Inline
# ============================================================


class OrderItemInline(admin.TabularInline):
    model = OrderItem

    extra = 0

    fields = (
        "product_name",
        "variant_name",
        "selection_type",
        "measurement_display",
        "quantity",
        "unit_price",
        "mrp",
        "line_total",
    )

    readonly_fields = (
        "product_name",
        "variant_name",
        "selection_type",
        "measurement_display",
        "quantity",
        "unit_price",
        "mrp",
        "line_total",
    )

    ordering = (
        "created_at",
    )

    show_change_link = True

    def has_add_permission(
        self,
        request,
        obj=None,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False

    @admin.display(
        description="Measurement",
    )
    def measurement_display(self, obj):
        if not obj:
            return "-"

        if obj.variant_name:
            return obj.variant_name

        if obj.measurement_value is None:
            return "-"

        return (
            f"{obj.measurement_value} "
            f"{obj.unit}"
        )


# ============================================================
# Order Admin
# ============================================================


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):

    list_display = (
        "order_number",
        "user",
        "store",
        "status",
        "fullfillment_type",
        "item_count_display",
        "subtotal_display",
        "delivery_fee_display",
        "discount_display",
        "total_display",
        "created_at",
    )

    list_filter = (
        "status",
        "fullfillment_type",
        "store",
        "created_at",
    )

    search_fields = (
        "order_number",
        "user__username",
        "user__email",
        "store__name",
    )

    autocomplete_fields = (
        "user",
        "store",
    )

    ordering = (
        "-created_at",
    )

    list_per_page = 50

    date_hierarchy = "created_at"

    list_select_related = (
        "user",
        "store",
    )

    inlines = (
        OrderItemInline,
    )

    readonly_fields = (
        "id",
        "order_number",
        "user",
        "store",
        "fullfillment_type",
        "subtotal",
        "delivery_fee",
        "discount_amount",
        "total_amount",
        "item_count_display",
        "total_units_display",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Order",
            {
                "fields": (
                    "id",
                    "order_number",
                    "user",
                    "store",
                    "status",
                    "fullfillment_type",
                )
            },
        ),

        (
            "Summary",
            {
                "fields": (
                    "item_count_display",
                    "total_units_display",
                )
            },
        ),

        (
            "Pricing",
            {
                "fields": (
                    "subtotal",
                    "delivery_fee",
                    "discount_amount",
                    "total_amount",
                )
            },
        ),

        (
            "Notes",
            {
                "fields": (
                    "customer_note",
                    "cancellation_reason",
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

    @admin.display(
        description="Items",
    )
    def item_count_display(self, obj):
        if not obj.pk:
            return 0

        return obj.items.count()

    @admin.display(
        description="Units",
    )
    def total_units_display(self, obj):
        if not obj.pk:
            return 0

        return sum(
            item.quantity
            for item in obj.items.all()
        )

    @admin.display(
        description="Subtotal",
        ordering="subtotal",
    )
    def subtotal_display(self, obj):
        return f"₹{obj.subtotal}"

    @admin.display(
        description="Delivery Fee",
        ordering="delivery_fee",
    )
    def delivery_fee_display(self, obj):
        if not obj.delivery_fee:
            return "-"

        return f"â‚¹{obj.delivery_fee}"

    @admin.display(
        description="Discount",
        ordering="discount_amount",
    )
    def discount_display(self, obj):
        if not obj.discount_amount:
            return "-"

        return f"₹{obj.discount_amount}"

    @admin.display(
        description="Total",
        ordering="total_amount",
    )
    def total_display(self, obj):
        return f"₹{obj.total_amount}"

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
            )
        )

    def has_add_permission(self, request):
        # Orders should only be created through checkout.
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        # Better to retain order history.
        return False


# ============================================================
# Order Item Admin
# ============================================================


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):

    list_display = (
        "product_name",
        "order_number_display",
        "variant_name",
        "selection_type",
        "measurement_display",
        "quantity",
        "unit_price_display",
        "line_total_display",
        "created_at",
    )

    list_filter = (
        "selection_type",
        "measurement_type",
        "unit",
        "created_at",
    )

    search_fields = (
        "product_name",
        "product_public_id",
        "variant_name",
        "order__order_number",
    )

    autocomplete_fields = (
        "order",
        "product",
        "variant",
    )

    ordering = (
        "-created_at",
    )

    list_per_page = 50

    list_select_related = (
        "order",
        "product",
        "variant",
    )

    readonly_fields = (
        "id",
        "order",
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
        "total_measurement_display",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Order",
            {
                "fields": (
                    "id",
                    "order",
                )
            },
        ),

        (
            "Product Reference",
            {
                "fields": (
                    "product",
                    "variant",
                )
            },
        ),

        (
            "Snapshot",
            {
                "fields": (
                    "selection_type",
                    "product_public_id",
                    "product_name",
                    "variant_name",
                )
            },
        ),

        (
            "Measurement",
            {
                "fields": (
                    "measurement_type",
                    "measurement_value",
                    "unit",
                    "pack_count",
                    "quantity",
                    "total_measurement_display",
                )
            },
        ),

        (
            "Pricing",
            {
                "fields": (
                    "unit_price",
                    "mrp",
                    "line_total",
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

    @admin.display(
        description="Order",
        ordering="order__order_number",
    )
    def order_number_display(self, obj):
        return obj.order.order_number

    @admin.display(
        description="Measurement",
    )
    def measurement_display(self, obj):
        if obj.variant_name:
            return obj.variant_name

        if obj.measurement_value is None:
            return "-"

        return (
            f"{obj.measurement_value} "
            f"{obj.unit}"
        )

    @admin.display(
        description="Total Measurement",
    )
    def total_measurement_display(self, obj):
        total = obj.total_measurement_value

        if total is None:
            return "-"

        if not obj.unit:
            return str(total)

        return f"{total} {obj.unit}"

    @admin.display(
        description="Unit Price",
        ordering="unit_price",
    )
    def unit_price_display(self, obj):
        return f"₹{obj.unit_price}"

    @admin.display(
        description="Line Total",
        ordering="line_total",
    )
    def line_total_display(self, obj):
        return f"₹{obj.line_total}"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False
