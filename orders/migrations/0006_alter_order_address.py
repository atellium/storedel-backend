from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("locations", "0002_address"),
        ("orders", "0005_orderitem_is_not_available"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="address",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="orders",
                to="locations.address",
            ),
        ),
    ]
