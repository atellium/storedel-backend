from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("carts", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="cartitem",
            name="unit_price",
        ),
    ]
