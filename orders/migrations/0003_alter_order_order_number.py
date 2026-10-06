import secrets
import string

from django.db import migrations, models


ORDER_NUMBER_ALPHABET = string.ascii_uppercase + string.digits


def rebuild_legacy_order_numbers(apps, schema_editor):
    order_model = apps.get_model("orders", "Order")
    serials_by_store_day = {}
    used_order_numbers = set()

    orders = (
        order_model.objects.select_related("store")
        .order_by("store_id", "created_at", "id")
    )

    for order in orders:
        store_code = get_store_code(order.store)
        order_day = order.created_at.date()
        serial_key = (order.store_id, order_day)
        serial = serials_by_store_day.get(serial_key, 0) + 1
        serials_by_store_day[serial_key] = serial

        order_number = build_order_number(store_code, serial, used_order_numbers)
        used_order_numbers.add(order_number)

        if order.order_number != order_number:
            order.order_number = order_number
            order.save(update_fields=["order_number"])


def get_store_code(store):
    store_code = (getattr(store, "code", "") or "").upper()[:3]
    if len(store_code) == 3:
        return store_code

    name_code = "".join(
        char for char in (getattr(store, "name", "") or "").upper()
        if char in ORDER_NUMBER_ALPHABET
    )[:3]
    return name_code.ljust(3, "X")


def build_order_number(store_code, serial, used_order_numbers):
    while True:
        random_code = "".join(
            secrets.choice(ORDER_NUMBER_ALPHABET)
            for _ in range(3)
        )
        order_number = f"{store_code}{random_code}{serial:04d}"
        if order_number not in used_order_numbers:
            return order_number


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_order_delivery_fee_order_fullfillment_type"),
    ]

    operations = [
        migrations.RunPython(
            rebuild_legacy_order_numbers,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="order",
            name="order_number",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                editable=False,
                max_length=10,
                unique=True,
            ),
        ),
    ]
