import secrets
import string
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import TimestampedModel


# ============================================================
# Helpers
# ============================================================

ORDER_NUMBER_ALPHABET = (
    string.ascii_uppercase
    + string.digits
)


def generate_order_number(store=None):
    if store is not None:
        return generate_store_order_number(store)

    return "".join(
        secrets.choice(ORDER_NUMBER_ALPHABET)
        for _ in range(10)
    )


def generate_store_order_number(store):
    store_code = (store.code or "").upper()[:3]
    if len(store_code) != 3:
        raise ValidationError({
            "store": "Store code must include at least 3 characters."
        })

    today = timezone.localdate()
    serial = get_next_daily_order_serial(store, today)
    random_code = "".join(
        secrets.choice(ORDER_NUMBER_ALPHABET)
        for _ in range(3)
    )

    return f"{store_code}{random_code}{serial:04d}"


def get_next_daily_order_serial(store, date):
    max_serial = 0
    order_numbers = Order.objects.filter(
        store=store,
        created_at__date=date,
        order_number__startswith=(store.code or "").upper()[:3],
    ).values_list("order_number", flat=True)

    for order_number in order_numbers:
        if len(order_number) != 10:
            continue

        serial = order_number[-4:]
        if serial.isdigit():
            max_serial = max(max_serial, int(serial))

    next_serial = max_serial + 1
    if next_serial > 9999:
        raise ValidationError({
            "order_number": "Daily order serial limit reached for this store."
        })

    return next_serial


# ============================================================
# Order
# ============================================================


class Order(TimestampedModel):

    class Status(models.TextChoices):
        PLACED = "placed", "Placed"
        ACCEPTED = "accepted", "Accepted"
        PREPARING = "preparing", "Preparing"
        READY = "ready", "Ready"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        REJECTED = "rejected", "Rejected"

    class FullfillmentType(models.TextChoices):
        SCHEDULED_DELIVERY = "scheduled_delivery", "Scheduled Delivery"
        EXPRESS_DELIVERY = "express_delivery", "Express Delivery"
        PICKUP = "pickup", "Pickup" 

    class PaymentType(models.TextChoices):
        CASH = "cash", "Cash"
        ONLINE = "online", "Online"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    order_number = models.CharField(
        max_length=10,
        unique=True,
        blank=True,
        default="",
        editable=False,
        db_index=True,
    )

    # --------------------------------------------------------
    # Customer
    # --------------------------------------------------------

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )

    # --------------------------------------------------------
    # Store
    # --------------------------------------------------------

    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.PROTECT,
        related_name="orders",
    )

    address = models.ForeignKey(
        "locations.Address",
        on_delete=models.PROTECT,
        related_name="orders",
        null=True,
        blank=True,
    )

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLACED,
        db_index=True,
    )

    # --------------------------------------------------------
    # Fullfillment
    # --------------------------------------------------------

    fullfillment_type = models.CharField(
        max_length=20,
        choices=FullfillmentType.choices,
        default=FullfillmentType.SCHEDULED_DELIVERY,
        db_index=True,
    )

    # --------------------------------------------------------
    # Pricing
    #
    # Stored in whole rupees.
    # --------------------------------------------------------

    subtotal = models.PositiveIntegerField(
        default=0,
    )

    delivery_fee = models.PositiveIntegerField(
        default=0,
    )

    discount_amount = models.PositiveIntegerField(
        default=0,
    )

    total_amount = models.PositiveIntegerField(
        default=0,
    )

    # --------------------------------------------------------
    # Notes
    # --------------------------------------------------------

    customer_note = models.CharField(
        max_length=500,
        blank=True,
    )

    cancellation_reason = models.CharField(
        max_length=500,
        blank=True,
    )

    # --------------------------------------------------------
    # Payment
    # --------------------------------------------------------

    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        default=PaymentType.CASH,
        db_index=True,
    )

    class Meta:
        db_table = "orders"

        ordering = [
            "-created_at",
        ]

        indexes = [
            models.Index(
                fields=[
                    "user",
                    "status",
                ],
                name="order_user_status_idx",
            ),
            models.Index(
                fields=[
                    "store",
                    "status",
                ],
                name="order_store_status_idx",
            ),
            models.Index(
                fields=[
                    "store",
                    "created_at",
                ],
                name="order_store_date_idx",
            ),
        ]

        verbose_name = "Order"
        verbose_name_plural = "Orders"

    def __str__(self):
        return self.order_number

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = generate_store_order_number(self.store)

        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()

        expected_total = self.calculate_total()

        if expected_total < 0:
            raise ValidationError({
                "discount_amount": (
                    "Discount cannot exceed subtotal."
                )
            })

        if self.total_amount != expected_total:
            raise ValidationError({
                "total_amount": (
                    f"Total amount should be "
                    f"₹{expected_total}."
                )
            })

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
    def not_available_amount(self):
        if self.pk is None:
            return 0

        return sum(
            item.line_total
            for item in self.items.all()
            if item.is_not_available
        )

    def calculate_total(self):
        return max(
            0,
            self.subtotal
            + self.delivery_fee
            - self.discount_amount
            - self.not_available_amount,
        )


# ============================================================
# Order Item
# ============================================================


class OrderItem(TimestampedModel):

    class SelectionType(models.TextChoices):
        VARIANT = "variant", "Variant"
        CUSTOM = "custom", "Custom Quantity"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )

    # --------------------------------------------------------
    # Current references
    #
    # SET_NULL because the historical order must remain
    # even if a product/variant gets deleted later.
    # --------------------------------------------------------

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )

    variant = models.ForeignKey(
        "products.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )

    # --------------------------------------------------------
    # Selection
    # --------------------------------------------------------

    selection_type = models.CharField(
        max_length=20,
        choices=SelectionType.choices,
    )

    # --------------------------------------------------------
    # Product snapshots
    # --------------------------------------------------------

    product_public_id = models.CharField(
        max_length=8,
        blank=True,
    )

    product_name = models.CharField(
        max_length=200,
    )

    variant_name = models.CharField(
        max_length=120,
        blank=True,
    )

    # --------------------------------------------------------
    # Measurement snapshots
    # --------------------------------------------------------

    measurement_type = models.CharField(
        max_length=20,
        blank=True,
    )

    # Lowest-unit measurement.
    #
    # 500 g  -> 500
    # 1 kg   -> 1000
    # 750 ml -> 750
    # 6 Pcs  -> 6
    measurement_value = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    # g / ml / piece / pack / box / jar / can / etc.
    unit = models.CharField(
        max_length=20,
        blank=True,
    )

    # Example:
    #
    # Lux Soap
    # 75 g × 3
    #
    # measurement_value = 75
    # pack_count = 3
    pack_count = models.PositiveIntegerField(
        default=1,
    )

    # --------------------------------------------------------
    # Quantity
    #
    # Number of sellable units/bundles.
    # --------------------------------------------------------

    quantity = models.PositiveIntegerField(
        default=1,
    )

    # --------------------------------------------------------
    # Price snapshot
    #
    # Important:
    # unlike CartItem, prices MUST be stored here.
    # --------------------------------------------------------

    unit_price = models.PositiveIntegerField()

    mrp = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    line_total = models.PositiveIntegerField()

    is_not_available = models.BooleanField(
        default=False,
    )
    is_ready = models.BooleanField(
        default=False,
    )



    class Meta:
        db_table = "order_items"

        ordering = [
            "created_at",
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    quantity__gt=0
                ),
                name="order_item_quantity_gt_zero",
            ),

            models.CheckConstraint(
                condition=Q(
                    pack_count__gt=0
                ),
                name="order_item_pack_count_gt_zero",
            ),

            models.CheckConstraint(
                condition=(
                    Q(measurement_value__isnull=True)
                    | Q(measurement_value__gt=0)
                ),
                name="order_item_measure_value_gt_zero",
            ),

            models.CheckConstraint(
                condition=(
                    Q(mrp__isnull=True)
                    | Q(
                        mrp__gte=models.F(
                            "unit_price"
                        )
                    )
                ),
                name="order_item_mrp_gte_price",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "order",
                    "product",
                ],
                name="order_item_product_idx",
            ),
        ]

        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"

    def __str__(self):
        if self.variant_name:
            return (
                f"{self.product_name} - "
                f"{self.variant_name} "
                f"× {self.quantity}"
            )

        return (
            f"{self.product_name} "
            f"× {self.quantity}"
        )

    def clean(self):
        super().clean()

        expected_total = (
            self.unit_price
            * self.quantity
        )

        if self.line_total != expected_total:
            raise ValidationError({
                "line_total": (
                    f"Line total should be "
                    f"₹{expected_total}."
                )
            })

    @property
    def total_measurement_value(self):
        if self.measurement_value is None:
            return None

        return (
            self.measurement_value
            * self.pack_count
            * self.quantity
        )

    @property
    def discount_amount(self):
        if (
            self.mrp is not None
            and self.mrp > self.unit_price
        ):
            return (
                self.mrp
                - self.unit_price
            ) * self.quantity

        return 0
