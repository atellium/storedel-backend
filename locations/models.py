import uuid

from django.core.validators import RegexValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.conf import settings
from django.core.exceptions import ValidationError

from core.models import TimestampedModel

state_code_validator = RegexValidator(
    regex=r"^[A-Z]{2}$",
    message="Enter a two-letter uppercase state code.",
)

class State(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    code = models.CharField(
        max_length=2,
        unique=True,
        validators=[state_code_validator],
    )

    class Meta:
        ordering = ("name",)
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return self.name


class City(models.Model):
    class CityTier(models.IntegerChoices):
        TIER_1 = 1, "Tier 1"
        TIER_2 = 2, "Tier 2"
        TIER_3 = 3, "Tier 3"
        TIER_4 = 4, "Tier 4"

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)

    state = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        related_name="cities",
    )

    tier = models.PositiveSmallIntegerField(
        choices=CityTier.choices,
        default=CityTier.TIER_2,
    )

    pincode_prefixes = models.JSONField(
        default=list, 
        blank=True
    )

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "Cities"

        constraints = [
            models.UniqueConstraint(
                fields=["state", "slug"],
                name="unique_city_slug_per_state",
            ),
        ]

        indexes = [
            models.Index(fields=["state", "name"]),
            models.Index(fields=["state", "slug"]),
            models.Index(fields=["tier"]),
        ]

    def __str__(self):
        return f"{self.name}, {self.state.name}"


class Address(TimestampedModel):
    class AddressType(models.TextChoices):
        HOME = "home", "Home"
        WORK = "work", "Work"
        OTHER = "other", "Other"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="addresses",
    )

    # Label
    address_type = models.CharField(
        max_length=20,
        choices=AddressType.choices,
        default=AddressType.HOME,
    )

    custom_label = models.CharField(
        max_length=50,
        blank=True,
        help_text="Example: Parents' House, Warehouse",
    )

    # Receiver
    recipient_name = models.CharField(
        max_length=100,
    )

    phone = models.CharField(
        max_length=10,
        validators=[
            RegexValidator(
                regex=r"^[6-9]\d{9}$",
                message="Enter a valid 10-digit Indian mobile number.",
            )
        ],
    )

    # Address
    address_line1 = models.CharField(
        max_length=255,
        help_text="House/Flat number, building, street",
    )

    address_line2 = models.CharField(
        max_length=255,
        blank=True,
        help_text="Area, locality, colony, apartment, etc.",
    )

    landmark = models.CharField(
        max_length=150,
        blank=True,
    )

    city = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        related_name="user_addresses",
    )

    postal_code = models.CharField(
        max_length=10,
        db_index=True,
    )

    # Location
    latitude = models.DecimalField(
        max_digits=12,
        decimal_places=9,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-90),
            MaxValueValidator(90),
        ],
    )

    longitude = models.DecimalField(
        max_digits=12,
        decimal_places=9,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-180),
            MaxValueValidator(180),
        ],
    )

    # Preferences
    is_default = models.BooleanField(
        default=False,
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        ordering = ("-is_default", "-created_at")

        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(is_default=True),
                name="unique_default_address_per_user",
            ),
        ]

        indexes = [
            models.Index(
                fields=["user", "is_active"],
                name="address_user_active_idx",
            ),
            models.Index(
                fields=["user", "postal_code"],
                name="address_user_postcode_idx",
            ),
            models.Index(
                fields=["city", "postal_code"],
                name="address_city_postcode_idx",
            ),
        ]

    def __str__(self):
        return f"{self.recipient_name} - {self.address_line1}, {self.city}"

    def clean(self):
        super().clean()

        if (
            self.address_type == self.AddressType.OTHER
            and not self.custom_label.strip()
        ):
            raise ValidationError(
                {
                    "custom_label": (
                        "Custom label is required when address type is Other."
                    )
                }
            )

        # Avoid storing a custom label for Home/Work accidentally
        if self.address_type != self.AddressType.OTHER:
            self.custom_label = ""

        # Latitude and longitude should normally be present together
        if (self.latitude is None) != (self.longitude is None):
            raise ValidationError(
                "Both latitude and longitude must be provided together."
            )

    @property
    def label(self):
        if (
            self.address_type == self.AddressType.OTHER
            and self.custom_label
        ):
            return self.custom_label

        return self.get_address_type_display()

    @property
    def full_address(self):
        parts = [
            self.address_line1,
            self.address_line2,
            self.landmark,
            str(self.city),
            self.postal_code,
        ]

        return ", ".join(
            str(part).strip()
            for part in parts
            if part and str(part).strip()
        )