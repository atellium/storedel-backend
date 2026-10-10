import uuid

import pygeohash as pgh
from django.conf import settings
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.image_service import compress_image
from core.utils import generate_unique_slug
from core.models import TimestampedModel


class Store(TimestampedModel):
    #Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="stores")
    name = models.CharField(max_length=200)
    title = models.CharField(max_length=200, blank=True, default="")
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    code = models.CharField(max_length=10, unique=True, blank=True, default="")
    host_name = models.CharField(max_length=100, unique=True, null=True, blank=True, default="") # Hostname(blank=True, default="")

    # Location
    address = models.CharField(max_length=300)
    locality = models.CharField(max_length=100, blank=True, default="")
    city = models.ForeignKey(
        "locations.City",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stores",
    )
    pincode = models.CharField(max_length=6, blank=True, default="", db_index=True)
    latitude = models.DecimalField(
        max_digits=12,
        decimal_places=9,
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        max_digits=12,
        decimal_places=9,
        null=True,
        blank=True,
    )
    geohash = models.CharField(max_length=12, blank=True, default="", db_index=True)

    # Contact
    phone = models.CharField(max_length=16, blank=True, default="")
    whatsapp = models.CharField(max_length=16, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    website = models.URLField(blank=True, default="")

    # Media
    cover_image  = models.ImageField(
        upload_to="stores/",
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["jpg", "jpeg", "png", "webp"]
            )
        ],
    )

    # Schedule
    store_hours = models.JSONField(blank=True, default=dict)

    # Catalog
    categories = models.ManyToManyField(
        "products.ProductCategory",
        through="stores.StoreCategory",
        related_name="stores",
        blank=True,
    )

    #Status 
    is_active = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "stores"
        ordering = ("name", "id")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if self.cover_image and not self.cover_image._committed:
            processed_image = compress_image(
                self.cover_image,
                max_width=640,
                quality=85,
                convert_to_webp=True,
            )
            processed_image.name = f"cover/{uuid.uuid4().hex}.webp"
            self.cover_image = processed_image
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"cover_image"}

        if not self.geohash and self.latitude is not None and self.longitude is not None:
            self.geohash = pgh.encode(
                float(self.latitude),
                float(self.longitude),
                precision=12,
            )
            if update_fields is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"geohash"}

        should_generate_slug = (
            self._state.adding
            or not self.slug
            or update_fields is None
            or bool({"name", "locality"} & set(update_fields))
        )
        if should_generate_slug:
            self.slug = generate_unique_slug(
                self,
                " ".join(part for part in (self.name, self.locality) if part),
                fallback="store",
                using=kwargs.get("using"),
            )
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"slug"}
        return super().save(*args, **kwargs)


class StoreCategory(TimestampedModel):
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="category_relations",
    )
    category = models.ForeignKey(
        "products.ProductCategory",
        on_delete=models.CASCADE,
        related_name="store_relations",
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        db_index=True,
    )

    class Meta:
        db_table = "store_categories"
        ordering = (
            "sort_order",
            "category__name",
        )
        constraints = [
            models.UniqueConstraint(
                fields=["store", "category"],
                name="unique_store_category",
            )
        ]

    def __str__(self):
        return f"{self.store} - {self.category}"


class SavedStore(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_store_relations",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="saved_by_users",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "store"],
                name="unique_user_saved_store",
            )
        ]

    def __str__(self):
        return f"{self.user} saved {self.store}"


class StoreSettings(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    store = models.OneToOneField(
        "stores.Store",
        on_delete=models.CASCADE,
        related_name="settings",
    )

    # ============================================================
    # ORDERING
    # ============================================================

    is_open = models.BooleanField(
        default=True,
        help_text="Whether the store is currently accepting orders.",
    )

    # ============================================================
    # FULFILLMENT METHODS
    # ============================================================

    is_pickup_enabled = models.BooleanField(
        default=True,
    )

    is_express_delivery_enabled = models.BooleanField(
        default=True,
    )

    is_scheduled_delivery_enabled = models.BooleanField(
        default=True,
    )

    # ============================================================
    # SCHEDULED DELIVERY
    # ============================================================

    scheduled_delivery_range_km = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Scheduled Delivery Range (KM)",
    )

    scheduled_min_order_amount = models.PositiveIntegerField(
        default=0,
        verbose_name="Scheduled Delivery Minimum Order Amount",
    )

    scheduled_delivery_charge = models.PositiveIntegerField(
        default=0,
        verbose_name="Scheduled Delivery Charge",
    )

    scheduled_delivery_slots = models.JSONField(
        default=dict,
        blank=True,
        help_text="Recurring scheduled delivery slots.",
    )

    scheduled_delivery_disable_till = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Scheduled delivery remains temporarily unavailable "
            "until this date and time."
        ),
    )

    # ============================================================
    # EXPRESS DELIVERY
    # ============================================================

    express_delivery_range_km = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Express Delivery Range (KM)",
    )

    express_min_order_amount = models.PositiveIntegerField(
        default=0,
        verbose_name="Express Delivery Minimum Order Amount",
    )

    express_delivery_charge = models.PositiveIntegerField(
        default=0,
        verbose_name="Express Delivery Charge",
    )

    express_delivery_disable_till = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Express delivery remains temporarily unavailable "
            "until this date and time."
        ),
    )

    express_min_delivery_minutes = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(1)],
    )

    express_max_delivery_minutes = models.PositiveIntegerField(
        default=45,
        validators=[MinValueValidator(1)],
    )

    # ============================================================
    # PICKUP
    # ============================================================

    pickup_min_order_amount = models.PositiveIntegerField(
        default=0,
        verbose_name="Pickup Minimum Order Amount",
    )

    pickup_disable_till = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Pickup remains temporarily unavailable "
            "until this date and time."
        ),
    )

    pickup_min_preparation_minutes = models.PositiveIntegerField(
        default=15,
        validators=[MinValueValidator(1)],
    )

    pickup_max_preparation_minutes = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(1)],
    )

    # ============================================================
    # LICENCING
    # ============================================================

    fssai = models.CharField(
        max_length=100,
        blank=True,
        help_text="FSSAI License Number",
    )

    gst = models.CharField(
        max_length=100,
        blank=True,
        help_text="GST Number",
    )

    # ============================================================
    # VALIDATION
    # ============================================================

    def clean(self):
        super().clean()

        errors = {}

        # Express delivery duration
        if (
            self.express_max_delivery_minutes
            < self.express_min_delivery_minutes
        ):
            errors["express_max_delivery_minutes"] = (
                "Maximum express delivery time must be greater than "
                "or equal to minimum delivery time."
            )

        # Pickup preparation duration
        if (
            self.pickup_max_preparation_minutes
            < self.pickup_min_preparation_minutes
        ):
            errors["pickup_max_preparation_minutes"] = (
                "Maximum pickup preparation time must be greater than "
                "or equal to minimum preparation time."
            )

        # Express range
        if (
            self.is_express_delivery_enabled
            and self.express_delivery_range_km <= 0
        ):
            errors["express_delivery_range_km"] = (
                "Express delivery range must be greater than 0."
            )

        # Scheduled range
        if (
            self.is_scheduled_delivery_enabled
            and self.scheduled_delivery_range_km <= 0
        ):
            errors["scheduled_delivery_range_km"] = (
                "Scheduled delivery range must be greater than 0."
            )

        # At least one method enabled
        if not any(
            (
                self.is_pickup_enabled,
                self.is_express_delivery_enabled,
                self.is_scheduled_delivery_enabled,
            )
        ):
            errors["is_pickup_enabled"] = (
                "At least one fulfillment method must be enabled."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    # ============================================================
    # INTERNAL HELPERS
    # ============================================================

    @staticmethod
    def _is_disabled_till(disable_till):
        if not disable_till:
            return False

        return timezone.now() < disable_till

    # ============================================================
    # TEMPORARY DISABLE STATUS
    # ============================================================

    @property
    def is_pickup_temporarily_disabled(self):
        return self._is_disabled_till(
            self.pickup_disable_till
        )

    @property
    def is_express_delivery_temporarily_disabled(self):
        return self._is_disabled_till(
            self.express_delivery_disable_till
        )

    @property
    def is_scheduled_delivery_temporarily_disabled(self):
        return self._is_disabled_till(
            self.scheduled_delivery_disable_till
        )

    # ============================================================
    # AVAILABILITY
    # ============================================================

    @property
    def accepts_pickup(self):
        return (
            self.is_open
            and self.is_pickup_enabled
            and not self.is_pickup_temporarily_disabled
        )

    @property
    def accepts_express_delivery(self):
        return (
            self.is_open
            and self.is_express_delivery_enabled
            and not self.is_express_delivery_temporarily_disabled
        )

    @property
    def accepts_scheduled_delivery(self):
        return (
            self.is_open
            and self.is_scheduled_delivery_enabled
            and not self.is_scheduled_delivery_temporarily_disabled
        )

    @property
    def has_available_fulfillment_method(self):
        return any(
            (
                self.accepts_pickup,
                self.accepts_express_delivery,
                self.accepts_scheduled_delivery,
            )
        )

    # ============================================================
    # META
    # ============================================================

    class Meta:
        db_table = "store_settings"
        verbose_name = "Store Settings"
        verbose_name_plural = "Store Settings"

    def __str__(self):
        return f"Settings for {self.store}"


