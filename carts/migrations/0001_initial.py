# Generated manually from carts.models.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("products", "0003_alter_productvariant_options_and_more"),
        ("stores", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Cart",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="carts",
                        to="stores.store",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="carts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Cart",
                "verbose_name_plural": "Carts",
                "db_table": "carts",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="CartItem",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("custom_value", models.PositiveIntegerField(blank=True, null=True)),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("unit_price", models.PositiveIntegerField(editable=False)),
                (
                    "cart",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="carts.cart",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cart_items",
                        to="products.product",
                    ),
                ),
                (
                    "variant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cart_items",
                        to="products.productvariant",
                    ),
                ),
            ],
            options={
                "verbose_name": "Cart Item",
                "verbose_name_plural": "Cart Items",
                "db_table": "cart_items",
                "ordering": ["created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="cart",
            index=models.Index(
                fields=["user", "is_active"],
                name="cart_user_active_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="cart",
            index=models.Index(
                fields=["store", "is_active"],
                name="cart_store_active_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="cart",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_active", True)),
                fields=("user", "store"),
                name="unique_active_user_cart_per_store",
            ),
        ),
        migrations.AddIndex(
            model_name="cartitem",
            index=models.Index(
                fields=["cart", "product"],
                name="cart_item_product_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="cartitem",
            index=models.Index(
                fields=["cart", "variant"],
                name="cart_item_variant_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="cartitem",
            constraint=models.CheckConstraint(
                condition=(
                    (
                        models.Q(("variant__isnull", False))
                        & models.Q(("custom_value__isnull", True))
                    )
                    | (
                        models.Q(("variant__isnull", True))
                        & models.Q(("custom_value__isnull", False))
                    )
                ),
                name="cart_item_variant_or_custom",
            ),
        ),
        migrations.AddConstraint(
            model_name="cartitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("quantity__gt", 0)),
                name="cart_item_quantity_gt_zero",
            ),
        ),
        migrations.AddConstraint(
            model_name="cartitem",
            constraint=models.UniqueConstraint(
                condition=models.Q(("variant__isnull", False)),
                fields=("cart", "variant"),
                name="unique_cart_variant",
            ),
        ),
        migrations.AddConstraint(
            model_name="cartitem",
            constraint=models.UniqueConstraint(
                condition=(
                    models.Q(("custom_value__isnull", False))
                    & models.Q(("variant__isnull", True))
                ),
                fields=("cart", "product", "custom_value"),
                name="unique_cart_custom_quantity",
            ),
        ),
    ]
