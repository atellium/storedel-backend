from django.contrib import admin

from locations.models import City, State, Address


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "slug")
    search_fields = ("name", "code", "slug")
    ordering = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    list_per_page = 50


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "state", "tier", "slug", "pincode_prefixes_display")
    list_display_links = ("name",)
    list_editable = ("tier",)
    list_filter = ("tier", "state")
    search_fields = ("name", "slug", "state__name", "state__code")
    ordering = ("state__name", "name")
    autocomplete_fields = ("state",)
    prepopulated_fields = {"slug": ("name",)}
    list_select_related = ("state",)
    list_per_page = 50

    @admin.display(description="Pincode prefixes")
    def pincode_prefixes_display(self, obj):
        return ", ".join(obj.pincode_prefixes)


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = (
        "recipient_name",
        "user",
        "phone",
        "address_type",
        "city",
        "postal_code",
        "is_default",
        "is_active",
        "created_at",
    )

    list_filter = (
        "address_type",
        "is_default",
        "is_active",
        "city",
        "created_at",
    )

    search_fields = (
        "recipient_name",
        "phone",
        "address_line1",
        "address_line2",
        "landmark",
        "postal_code",
        "user__email",
        "user__phone",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "full_address_display",
        "location_display",
    )

    autocomplete_fields = (
        "user",
        "city",
    )

    ordering = (
        "-created_at",
    )

    list_per_page = 50

    date_hierarchy = "created_at"

    fieldsets = (
        (
            "User",
            {
                "fields": (
                    "id",
                    "user",
                ),
            },
        ),
        (
            "Address Label",
            {
                "fields": (
                    "address_type",
                    "custom_label",
                ),
            },
        ),
        (
            "Recipient",
            {
                "fields": (
                    "recipient_name",
                    "phone",
                ),
            },
        ),
        (
            "Address",
            {
                "fields": (
                    "address_line1",
                    "address_line2",
                    "landmark",
                    "city",
                    "postal_code",
                    "full_address_display",
                ),
            },
        ),
        (
            "Location",
            {
                "fields": (
                    "latitude",
                    "longitude",
                    "location_display",
                ),
            },
        ),
        (
            "Preferences",
            {
                "fields": (
                    "is_default",
                    "is_active",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    @admin.display(description="Full Address")
    def full_address_display(self, obj):
        if not obj.pk:
            return "-"
        return obj.full_address

    @admin.display(description="Location")
    def location_display(self, obj):
        if obj.latitude is None or obj.longitude is None:
            return "Location not set"

        return f"{obj.latitude}, {obj.longitude}"

    @admin.display(
        boolean=True,
        description="Default",
        ordering="is_default",
    )
    def default_status(self, obj):
        return obj.is_default