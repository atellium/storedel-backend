import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import TimestampedModel
from products.models import Product, ProductVariant


class Cart(TimestampedModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="carts",
    )

    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.CASCADE,
        related_name="carts",
    )

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    class Meta:
        db_table = "carts"

        ordering = [
            "-updated_at",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "user",
                    "store",
                ],
                condition=Q(is_active=True),
                name="unique_active_user_cart_per_store",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "user",
                    "is_active",
                ],
                name="cart_user_active_idx",
            ),
            models.Index(
                fields=[
                    "store",
                    "is_active",
                ],
                name="cart_store_active_idx",
            ),
        ]

        verbose_name = "Cart"
        verbose_name_plural = "Carts"

    def __str__(self):
        return f"{self.user} - {self.store}"

    @property
    def item_count(self):
        return self.items.count()

    @property
    def total_units(self):
        return sum(
            item.quantity
            for item in self.items.all()
        )

    @property
    def subtotal(self):
        return sum(
            item.total_price
            for item in self.items.all()
        )


class CartItem(TimestampedModel):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )

    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name="cart_items",
        null=True,
        blank=True,
    )

    # Used only for custom quantity products.
    # Stored in lowest unit:
    # gram / ml / piece.
    custom_value = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    # Number of selected packs / units.
    quantity = models.PositiveIntegerField(
        default=1,
    )

    class Meta:
        db_table = "cart_items"

        ordering = [
            "created_at",
        ]

        constraints = [
            # Either predefined variant OR custom value.
            models.CheckConstraint(
                condition=(
                    (
                        Q(variant__isnull=False)
                        & Q(custom_value__isnull=True)
                    )
                    |
                    (
                        Q(variant__isnull=True)
                        & Q(custom_value__isnull=False)
                    )
                ),
                name="cart_item_variant_or_custom",
            ),

            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="cart_item_quantity_gt_zero",
            ),

            # Same predefined variant should not create
            # multiple cart rows.
            models.UniqueConstraint(
                fields=[
                    "cart",
                    "variant",
                ],
                condition=Q(
                    variant__isnull=False
                ),
                name="unique_cart_variant",
            ),

            # Same custom measurement should merge.
            models.UniqueConstraint(
                fields=[
                    "cart",
                    "product",
                    "custom_value",
                ],
                condition=Q(
                    variant__isnull=True,
                    custom_value__isnull=False,
                ),
                name="unique_cart_custom_quantity",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "cart",
                    "product",
                ],
                name="cart_item_product_idx",
            ),
            models.Index(
                fields=[
                    "cart",
                    "variant",
                ],
                name="cart_item_variant_idx",
            ),
        ]

        verbose_name = "Cart Item"
        verbose_name_plural = "Cart Items"

    def __str__(self):
        if self.variant_id:
            return (
                f"{self.product.name} - "
                f"{self.variant.name} "
                f"× {self.quantity}"
            )

        return (
            f"{self.product.name} - "
            f"{self.display_custom_measurement} "
            f"× {self.quantity}"
        )

    def clean(self):
        super().clean()

        errors = {}

        if not self.cart_id or not self.product_id:
            return

        # Product must belong to same store as cart.
        if (
            self.product.store_id
            != self.cart.store_id
        ):
            errors["product"] = (
                "Product does not belong "
                "to this cart's store."
            )

        # Product must be active.
        if not self.product.is_active:
            errors["product"] = (
                "This product is not currently active."
            )

        # Predefined variant.
        if self.variant_id:
            if (
                self.variant.product_id
                != self.product_id
            ):
                errors["variant"] = (
                    "Variant does not belong "
                    "to the selected product."
                )

            if not self.variant.is_active:
                errors["variant"] = (
                    "This variant is not currently active."
                )

            if self.custom_value is not None:
                errors["custom_value"] = (
                    "Custom quantity cannot be used "
                    "with a predefined variant."
                )

        # Custom quantity.
        else:
            if self.custom_value is None:
                errors["custom_value"] = (
                    "Custom quantity is required."
                )

            elif not self.product.allow_custom_quantity:
                errors["custom_value"] = (
                    "This product does not support "
                    "custom quantities."
                )

            else:
                if self.matching_custom_variant is None:
                    try:
                        self.product.calculate_custom_price(
                            self.custom_value
                        )

                    except ValueError as exc:
                        errors["custom_value"] = str(exc)

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()

        super().save(*args, **kwargs)

    @property
    def unit_price(self):
        return self.calculate_unit_price()

    @property
    def matching_custom_variant(self):
        if self.custom_value is None or not self.product_id:
            return None

        return (
            self.product.variants.filter(
                value=self.custom_value,
                is_active=True,
            )
            .order_by(
                "pack_count",
                "sort_order",
                "id",
            )
            .first()
        )

    def calculate_unit_price(self):
        if self.variant_id:
            return self.variant.price

        if self.custom_value is not None:
            matching_variant = self.matching_custom_variant

            if matching_variant is not None:
                return matching_variant.price

            return (
                self.product
                .calculate_custom_price(
                    self.custom_value
                )
            )

        raise ValueError(
            "Cart item has no valid pricing source."
        )

    @property
    def total_price(self):
        if self.unit_price is None:
            return 0

        return self.unit_price * self.quantity

    @property
    def display_measurement(self):
        if self.variant_id:
            return self.variant.name

        return self.display_custom_measurement

    @property
    def display_custom_measurement(self):
        if self.custom_value is None:
            return ""

        measurement_type = (
            self.product.measurement_type
        )

        value = self.custom_value

        if (
            measurement_type
            == Product.MeasurementType.COUNT
        ):
            if value == 1:
                return "1 Piece"

            return f"{value} Pieces"

        if (
            measurement_type
            == Product.MeasurementType.WEIGHT
        ):
            if value < 1000:
                return f"{value} g"

            return (
                f"{self._format_thousand(value)} kg"
            )

        if (
            measurement_type
            == Product.MeasurementType.VOLUME
        ):
            if value < 1000:
                return f"{value} ml"

            return (
                f"{self._format_thousand(value)} L"
            )

        return str(value)

    @staticmethod
    def _format_thousand(value):
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

    @property
    def total_measurement_value(self):
        if self.variant_id:
            variant_total = (
                self.variant
                .total_measurement_value
            )

            if variant_total is None:
                return None

            return (
                variant_total
                * self.quantity
            )

        if self.custom_value is not None:
            return (
                self.custom_value
                * self.quantity
            )

        return None
