from django.contrib import admin

from .models import Store, StoreCategory, StoreSettings


class StoreCategoryInline(admin.TabularInline):
    model = StoreCategory
    extra = 1
    autocomplete_fields = (
        "category",
    )
    ordering = (
        "sort_order",
        "category__name",
    )


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner",
        "pincode",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
        "city",
        "published_at",
        "created_at",
    )

    search_fields = (
        "name",
        "slug",
        "phone",
        "whatsapp",
        "email",
        "address",
        "locality",
        "pincode",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    ordering = (
        "name",
    )

    list_select_related = (
        "owner",
        "city",
    )

    autocomplete_fields = (
        "owner",
        "city",
    )

    inlines = [
        StoreCategoryInline,
    ]

    prepopulated_fields = {
        "slug": ("name",),
    }

    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "id",
                    "owner",
                    "name",
                    "title",
                    "slug",
                    "code",
                    "host_name",
                )
            },
        ),
        (
            "Location",
            {
                "fields": (
                    "address",
                    "locality",
                    "city",
                    "pincode",
                    "latitude",
                    "longitude",
                    "geohash",
                )
            },
        ),
        (
            "Contact",
            {
                "fields": (
                    "phone",
                    "whatsapp",
                    "email",
                    "website",
                )
            },
        ),
        (
            "Media",
            {
                "fields": (
                    "cover_image",
                )
            },
        ),
        (
            "Store Hours",
            {
                "fields": (
                    "store_hours",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "is_active",
                    "published_at",
                )
            },
        ),
        (
            "System",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "store",
        "is_open",
        "is_pickup_enabled",
        "is_express_delivery_enabled",
        "is_scheduled_delivery_enabled",
        "has_available_fulfillment_method_display",
    )

    list_filter = (
        "is_open",
        "is_pickup_enabled",
        "is_express_delivery_enabled",
        "is_scheduled_delivery_enabled",
    )

    search_fields = (
        "store__name",
        "store__slug",
    )

    autocomplete_fields = (
        "store",
    )

    readonly_fields = (
        "accepts_pickup_display",
        "accepts_express_delivery_display",
        "accepts_scheduled_delivery_display",
        "is_pickup_temporarily_disabled_display",
        "is_express_delivery_temporarily_disabled_display",
        "is_scheduled_delivery_temporarily_disabled_display",
        "has_available_fulfillment_method_display",
    )

    fieldsets = (
        (
            "Store",
            {
                "fields": (
                    "store",
                    "is_open",
                )
            },
        ),
        (
            "Fulfillment Methods",
            {
                "fields": (
                    "is_pickup_enabled",
                    "is_express_delivery_enabled",
                    "is_scheduled_delivery_enabled",
                )
            },
        ),
        (
            "Pickup",
            {
                "fields": (
                    "pickup_min_order_amount",
                    "pickup_disable_till",
                    "pickup_min_preparation_minutes",
                    "pickup_max_preparation_minutes",
                )
            },
        ),
        (
            "Express Delivery",
            {
                "fields": (
                    "express_delivery_range_km",
                    "express_min_order_amount",
                    "express_delivery_charge",
                    "express_delivery_disable_till",
                    "express_min_delivery_minutes",
                    "express_max_delivery_minutes",
                )
            },
        ),
        (
            "Scheduled Delivery",
            {
                "fields": (
                    "scheduled_delivery_range_km",
                    "scheduled_min_order_amount",
                    "scheduled_delivery_charge",
                    "scheduled_delivery_slots",
                    "scheduled_delivery_disable_till",
                )
            },
        ),
        (
            "Current Availability",
            {
                "fields": (
                    "is_pickup_temporarily_disabled_display",
                    "is_express_delivery_temporarily_disabled_display",
                    "is_scheduled_delivery_temporarily_disabled_display",
                    "accepts_pickup_display",
                    "accepts_express_delivery_display",
                    "accepts_scheduled_delivery_display",
                    "has_available_fulfillment_method_display",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(
        boolean=True,
        description="Accepting Pickup",
    )
    def accepts_pickup_display(self, obj):
        return obj.accepts_pickup

    @admin.display(
        boolean=True,
        description="Accepting Express Delivery",
    )
    def accepts_express_delivery_display(self, obj):
        return obj.accepts_express_delivery

    @admin.display(
        boolean=True,
        description="Accepting Scheduled Delivery",
    )
    def accepts_scheduled_delivery_display(self, obj):
        return obj.accepts_scheduled_delivery

    @admin.display(
        boolean=True,
        description="Pickup Temporarily Disabled",
    )
    def is_pickup_temporarily_disabled_display(self, obj):
        return obj.is_pickup_temporarily_disabled

    @admin.display(
        boolean=True,
        description="Express Temporarily Disabled",
    )
    def is_express_delivery_temporarily_disabled_display(self, obj):
        return obj.is_express_delivery_temporarily_disabled

    @admin.display(
        boolean=True,
        description="Scheduled Temporarily Disabled",
    )
    def is_scheduled_delivery_temporarily_disabled_display(self, obj):
        return obj.is_scheduled_delivery_temporarily_disabled

    @admin.display(
        boolean=True,
        description="Has Available Fulfillment",
    )
    def has_available_fulfillment_method_display(self, obj):
        return obj.has_available_fulfillment_method
