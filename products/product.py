import secrets
import string
import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.text import slugify

from core.models import TimestampedModel
from uploads.models import Upload


PUBLIC_ID_ALPHABET = string.ascii_lowercase + string.digits


# ============================================================
# Helpers
# ============================================================


def generate_product_public_id():
    return "".join(
        secrets.choice(PUBLIC_ID_ALPHABET)
        for _ in range(8)
    )


def format_thousand_value(value: int) -> str:
    """
    Convert lowest-unit integer values into display values.

    Examples:
        1000 -> "1"
        1500 -> "1.5"
        1250 -> "1.25"
        1125 -> "1.125"
    """

    whole = value // 1000
    remainder = value % 1000

    if remainder == 0:
        return str(whole)

    decimal = (
        str(remainder)
        .rjust(3, "0")
        .rstrip("0")
    )

    return f"{whole}.{decimal}"


def round_price(value) -> int:
    """
    Round monetary value to nearest whole rupee.

    Uses ROUND_HALF_UP:

        16.49 -> 16
        16.50 -> 17
        16.51 -> 17
    """

    return int(
        Decimal(str(value)).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


# ============================================================
# Product
# ============================================================


class Product(TimestampedModel):

    class MeasurementType(models.TextChoices):
        NONE = "none", "No Measurement"
        COUNT = "count", "Count"
        WEIGHT = "weight", "Weight"
        VOLUME = "volume", "Volume"

    # --------------------------------------------------------
    # Identity
    # --------------------------------------------------------

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    public_id = models.CharField(
        max_length=8,
        unique=True,
        default=generate_product_public_id,
        editable=False,
        db_index=True,
    )

    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.CASCADE,
        related_name="products",
    )

    name = models.CharField(
        max_length=200,
    )

    slug = models.SlugField(
        max_length=255,
        unique=True,
    )

    short_description = models.CharField(
        max_length=300,
        blank=True,
    )

    # --------------------------------------------------------
    # Classification
    # --------------------------------------------------------

    categories = models.ManyToManyField(
        "products.ProductCategory",
        related_name="products",
        blank=True,
    )

    uploads = models.ManyToManyField(
        Upload,
        related_name="products",
        blank=True,
    )

    brand = models.CharField(
        max_length=120,
        blank=True,
        db_index=True,
    )

    # --------------------------------------------------------
    # Measurement
    # --------------------------------------------------------

    measurement_type = models.CharField(
        max_length=20,
        choices=MeasurementType.choices,
        default=MeasurementType.NONE,
        db_index=True,
        help_text=(
            "No Measurement = selling/package unit only, "
            "Count = numeric quantity of a selected unit, "
            "Weight = grams, "
            "Volume = millilitres."
        ),
    )

    # --------------------------------------------------------
    # Custom quantity
    #
    # Used mainly for loose products.
    #
    # Example:
    #
    # Sugar:
    # base_quantity = 1000
    # base_price = 50
    # minimum_quantity = 100
    # quantity_step = 50
    #
    # Means:
    # ₹50 per 1000 g
    # minimum 100 g
    # increments of 50 g
    # --------------------------------------------------------

    allow_custom_quantity = models.BooleanField(
        default=False,
        db_index=True,
    )

    base_quantity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Quantity corresponding to base_price. "
            "Stored in lowest unit: piece, gram or ml."
        ),
    )

    base_price = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Price in whole rupees for base_quantity."
        ),
    )

    minimum_quantity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Minimum custom quantity in lowest unit."
        ),
    )

    quantity_step = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Allowed custom quantity increment "
            "in lowest unit."
        ),
    )

    # --------------------------------------------------------
    # Flexible information
    # --------------------------------------------------------

    specifications = models.JSONField(
        default=dict,
        blank=True,
    )

    # --------------------------------------------------------
    # Controls
    # --------------------------------------------------------

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    is_featured = models.BooleanField(
        default=False,
        db_index=True,
    )

    sort_order = models.PositiveIntegerField(
        default=0,
        db_index=True,
    )

    class Meta:
        db_table = "products"

        ordering = [
            "sort_order",
            "-created_at",
        ]

        indexes = [
            models.Index(
                fields=[
                    "store",
                    "is_active",
                ],
                name="product_store_active_idx",
            ),
            models.Index(
                fields=[
                    "store",
                    "measurement_type",
                ],
                name="product_store_measure_idx",
            ),
            models.Index(
                fields=[
                    "store",
                    "is_featured",
                ],
                name="product_store_featured_idx",
            ),
            models.Index(
                fields=[
                    "store",
                    "allow_custom_quantity",
                ],
                name="product_store_custom_qty_idx",
            ),
        ]

        verbose_name = "Product"
        verbose_name_plural = "Products"

    def __str__(self):
        return self.name

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    def clean(self):
        super().clean()

        errors = {}

        if self.allow_custom_quantity:

            if (
                self.measurement_type
                == self.MeasurementType.NONE
            ):
                errors["allow_custom_quantity"] = (
                    "Products without a measurement "
                    "cannot allow custom quantity."
                )

            if not self.base_quantity:
                errors["base_quantity"] = (
                    "Base quantity is required when "
                    "custom quantity is enabled."
                )

            if self.base_price is None:
                errors["base_price"] = (
                    "Base price is required when "
                    "custom quantity is enabled."
                )

            if not self.minimum_quantity:
                errors["minimum_quantity"] = (
                    "Minimum quantity is required when "
                    "custom quantity is enabled."
                )

            if not self.quantity_step:
                errors["quantity_step"] = (
                    "Quantity step is required when "
                    "custom quantity is enabled."
                )

            if (
                self.base_quantity
                and self.minimum_quantity
                and self.minimum_quantity > self.base_quantity
            ):
                # This is allowed technically, but usually indicates
                # an incorrect setup.
                pass

        else:
            # Optional:
            # Keep custom-quantity fields empty when disabled.
            custom_fields = (
                "base_quantity",
                "base_price",
                "minimum_quantity",
                "quantity_step",
            )

            for field in custom_fields:
                if getattr(self, field) is not None:
                    errors[field] = (
                        "This field should be empty when "
                        "custom quantity is disabled."
                    )

        if errors:
            raise ValidationError(errors)

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = (
                slugify(self.name)[:220]
                or "product"
            )

            self.slug = (
                f"{base_slug}-{self.public_id}"
            )

        super().save(*args, **kwargs)

    # --------------------------------------------------------
    # Variant helpers
    # --------------------------------------------------------

    @property
    def default_variant(self):
        return (
            self.variants
            .filter(
                is_default=True,
                is_active=True,
            )
            .first()
        )

    @property
    def starting_price(self):
        variant = (
            self.variants
            .filter(is_active=True)
            .order_by("price")
            .first()
        )

        return (
            variant.price
            if variant
            else None
        )

    # --------------------------------------------------------
    # Custom quantity pricing
    # --------------------------------------------------------

    def calculate_custom_price(
        self,
        selected_quantity: int,
    ) -> int:
        """
        Calculate custom quantity price in whole rupees.

        Example:

        base_price = 55
        base_quantity = 1000 g

        selected = 300 g

        55 * 300 / 1000
        = 16.5
        = ₹17 after ROUND_HALF_UP
        """

        if not self.allow_custom_quantity:
            raise ValueError(
                "Custom quantity is not enabled "
                "for this product."
            )

        if selected_quantity < self.minimum_quantity:
            raise ValueError(
                "Selected quantity is below "
                "the minimum quantity."
            )

        amount = (
            Decimal(self.base_price)
            * Decimal(selected_quantity)
            / Decimal(self.base_quantity)
        )

        return int(
            amount.quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )


# ============================================================
# Product Variant
# ============================================================

class ProductVariant(TimestampedModel):

    class Unit(models.TextChoices):
        # Canonical measurement units
        GRAM = "g", "g"
        MILLILITRE = "ml", "ml"

        # Count / selling / packaging units
        PIECE = "piece", "Pcs"
        PACK = "pack", "Pack"
        BOX = "box", "Box"
        CARTON = "carton", "Carton"
        JAR = "jar", "Jar"
        CAN = "can", "Can"
        BOTTLE = "bottle", "Bottle"
        POUCH = "pouch", "Pouch"
        BAG = "bag", "Bag"
        TRAY = "tray", "Tray"
        TUBE = "tube", "Tube"
        ROLL = "roll", "Roll"

    # COUNT means value is meaningful: 6 Pcs, 10 Boxes, 6 Cans, etc.
    COUNT_UNITS = {
        Unit.PIECE,
        Unit.PACK,
        Unit.BOX,
        Unit.CARTON,
        Unit.JAR,
        Unit.CAN,
        Unit.BOTTLE,
        Unit.POUCH,
        Unit.BAG,
        Unit.TRAY,
        Unit.TUBE,
        Unit.ROLL,
    }

    # NONE means there is no numeric content/measurement value; only the
    # selling/package form matters: 1 Pack, 2 Jars, 1 Can, etc.
    NONE_UNITS = {
        Unit.PACK,
        Unit.BOX,
        Unit.CARTON,
        Unit.JAR,
        Unit.CAN,
        Unit.BOTTLE,
        Unit.POUCH,
        Unit.BAG,
        Unit.TRAY,
        Unit.TUBE,
        Unit.ROLL,
    }

    UNIT_LABELS = {
        Unit.PIECE: ("Pc", "Pcs"),
        Unit.PACK: ("Pack", "Packs"),
        Unit.BOX: ("Box", "Boxes"),
        Unit.CARTON: ("Carton", "Cartons"),
        Unit.JAR: ("Jar", "Jars"),
        Unit.CAN: ("Can", "Cans"),
        Unit.BOTTLE: ("Bottle", "Bottles"),
        Unit.POUCH: ("Pouch", "Pouches"),
        Unit.BAG: ("Bag", "Bags"),
        Unit.TRAY: ("Tray", "Trays"),
        Unit.TUBE: ("Tube", "Tubes"),
        Unit.ROLL: ("Roll", "Rolls"),
    }

    # --------------------------------------------------------
    # Identity
    # --------------------------------------------------------

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
    )

    # Automatically generated, e.g.:
    # 500 g
    # 1 kg
    # 75 g × 3
    # 250 ml × 6
    # 6 Pcs
    # 10 Boxes
    # 3 Packs
    name = models.CharField(
        max_length=120,
        editable=False,
    )

    # --------------------------------------------------------
    # Measurement / unit
    # --------------------------------------------------------

    # WEIGHT: lowest unit grams, e.g. 1000 = 1 kg
    # VOLUME: lowest unit ml, e.g. 1500 = 1.5 L
    # COUNT: number of selected unit, e.g. 6 + piece = 6 Pcs
    # NONE: value must be NULL; unit identifies selling/package form
    value = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    # WEIGHT and VOLUME are automatically normalized to g / ml.
    # COUNT and NONE are selected by the seller.
    unit = models.CharField(
        max_length=20,
        choices=Unit.choices,
    )

    # Number of identical measured/count groups sold together.
    # Examples:
    #   Soap 75 g:      value=75, unit=g, pack_count=1
    #   Soap 75 g x 3:  value=75, unit=g, pack_count=3
    #   6 cans x 2:     value=6, unit=can, pack_count=2
    #
    # For NONE, pack_count is the number of selected selling units:
    #   3 packs: value=None, unit=pack, pack_count=3
    pack_count = models.PositiveIntegerField(
        default=1,
    )

    # --------------------------------------------------------
    # Pricing - whole rupees
    # --------------------------------------------------------

    price = models.PositiveIntegerField(
        help_text="Selling price in whole rupees.",
    )

    mrp = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="MRP in whole rupees.",
    )

    cost_price = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Cost price in whole rupees.",
    )

    # --------------------------------------------------------
    # Controls
    # --------------------------------------------------------

    is_default = models.BooleanField(
        default=False,
        db_index=True,
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    class Meta:
        db_table = "product_variants"

        ordering = [
            "sort_order",
            "value",
            "unit",
            "pack_count",
        ]

        constraints = [
            # Measured / counted variants must be unique by product,
            # value, selected unit and bundle count.
            models.UniqueConstraint(
                fields=[
                    "product",
                    "value",
                    "unit",
                    "pack_count",
                ],
                condition=Q(value__isnull=False),
                name="unique_measured_product_variant",
            ),

            # NONE variants have no value, so unit + pack_count identifies
            # the option (e.g. 1 Jar vs 1 Box).
            models.UniqueConstraint(
                fields=[
                    "product",
                    "unit",
                    "pack_count",
                ],
                condition=Q(value__isnull=True),
                name="unique_unmeasured_product_variant",
            ),

            # Only one default variant per product.
            models.UniqueConstraint(
                fields=["product"],
                condition=Q(is_default=True),
                name="unique_default_variant_per_product",
            ),

            models.CheckConstraint(
                condition=(
                    Q(value__isnull=True)
                    | Q(value__gt=0)
                ),
                name="product_variant_value_gt_zero",
            ),

            models.CheckConstraint(
                condition=Q(pack_count__gt=0),
                name="product_variant_pack_count_gt_zero",
            ),

            models.CheckConstraint(
                condition=(
                    Q(mrp__isnull=True)
                    | Q(mrp__gte=models.F("price"))
                ),
                name="product_variant_mrp_gte_price",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "product",
                    "is_active",
                ],
                name="variant_product_active_idx",
            ),
            models.Index(
                fields=[
                    "product",
                    "value",
                    "unit",
                    "pack_count",
                ],
                name="variant_measure_pack_idx",
            ),
        ]

        verbose_name = "Product Variant"
        verbose_name_plural = "Product Variants"

    def __str__(self):
        return f"{self.product.name} - {self.name}"

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    def clean(self):
        super().clean()

        if not self.product_id:
            return

        # Normalize canonical units before validating them.
        self._set_unit()

        measurement_type = self.product.measurement_type
        errors = {}

        if measurement_type == Product.MeasurementType.WEIGHT:
            if self.value is None:
                errors["value"] = "Weight value is required."

            if self.unit != self.Unit.GRAM:
                errors["unit"] = "Weight must be stored in grams."

        elif measurement_type == Product.MeasurementType.VOLUME:
            if self.value is None:
                errors["value"] = "Volume value is required."

            if self.unit != self.Unit.MILLILITRE:
                errors["unit"] = "Volume must be stored in millilitres."

        elif measurement_type == Product.MeasurementType.COUNT:
            if self.value is None:
                errors["value"] = "Count value is required."

            if self.unit not in self.COUNT_UNITS:
                errors["unit"] = (
                    "Select a valid count unit such as Pcs, Pack, Box, "
                    "Can, Bottle or Carton."
                )

        elif measurement_type == Product.MeasurementType.NONE:
            if self.value is not None:
                errors["value"] = (
                    "Value must be empty when the product has no measurement."
                )

            if self.unit not in self.NONE_UNITS:
                errors["unit"] = (
                    "Select a valid selling/package unit such as Pack, Box, "
                    "Jar, Can or Carton."
                )

        if self.pack_count < 1:
            errors["pack_count"] = "Pack count must be at least 1."

        if self.mrp is not None and self.mrp < self.price:
            errors["mrp"] = "MRP cannot be lower than selling price."

        if errors:
            raise ValidationError(errors)

    # --------------------------------------------------------
    # Save / normalization
    # --------------------------------------------------------

    def save(self, *args, **kwargs):
        self._set_unit()
        self.name = self._generate_name()
        super().save(*args, **kwargs)

    def _set_unit(self):
        """
        Weight/volume use canonical lowest units.
        COUNT/NONE preserve the seller-selected unit.
        """
        if not self.product_id:
            return

        measurement_type = self.product.measurement_type

        if measurement_type == Product.MeasurementType.WEIGHT:
            self.unit = self.Unit.GRAM

        elif measurement_type == Product.MeasurementType.VOLUME:
            self.unit = self.Unit.MILLILITRE

    # --------------------------------------------------------
    # Display helpers
    # --------------------------------------------------------

    def _unit_label_for(self, amount: int) -> str:
        labels = self.UNIT_LABELS.get(self.unit)

        if not labels:
            return self.get_unit_display()

        singular, plural = labels
        return singular if amount == 1 else plural

    def _generate_name(self):
        measurement_type = self.product.measurement_type

        # No numeric content measurement: 1 Pack, 3 Jars, 2 Boxes...
        if measurement_type == Product.MeasurementType.NONE:
            label = self._unit_label_for(self.pack_count)
            return f"{self.pack_count} {label}"

        # Numeric count: 6 Pcs, 10 Boxes, 6 Cans...
        if measurement_type == Product.MeasurementType.COUNT:
            label = self._unit_label_for(self.value)
            count_display = f"{self.value} {label}"

            if self.pack_count > 1:
                return f"{count_display} (Pack of {self.pack_count})"

            return count_display

        # Weight / volume
        measurement = self.display_measurement

        if self.pack_count > 1:
            return f"{measurement} (Pack of {self.pack_count})"

        return measurement

    @property
    def display_measurement(self):
        measurement_type = self.product.measurement_type

        if measurement_type == Product.MeasurementType.NONE:
            label = self._unit_label_for(self.pack_count)
            return f"{self.pack_count} {label}"

        if measurement_type == Product.MeasurementType.COUNT:
            label = self._unit_label_for(self.value)
            return f"{self.value} {label}"

        if measurement_type == Product.MeasurementType.WEIGHT:
            if self.value < 1000:
                return f"{self.value} g"

            return f"{format_thousand_value(self.value)} kg"

        if measurement_type == Product.MeasurementType.VOLUME:
            if self.value < 1000:
                return f"{self.value} ml"

            return f"{format_thousand_value(self.value)} L"

        return ""

    @property
    def total_measurement_value(self):
        """
        Returns total lowest-unit content for measured/count products.

        75 g × 3   -> 225
        200 ml × 6 -> 1200
        6 cans × 2 -> 12

        NONE products return None because there is no numeric content value.
        """
        if self.value is None:
            return None

        return self.value * self.pack_count

    # --------------------------------------------------------
    # Price helpers
    # --------------------------------------------------------

    @property
    def discount_amount(self):
        if self.mrp and self.mrp > self.price:
            return self.mrp - self.price

        return 0

    @property
    def discount_percentage(self):
        if not self.mrp or self.mrp <= self.price:
            return 0

        return round(
            ((self.mrp - self.price) / self.mrp) * 100
        )
