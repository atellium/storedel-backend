from rest_framework import serializers

from locations.models import Address, City, State


class CityListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(
        required=False,
        max_length=100,
        trim_whitespace=True,
        allow_blank=False,
    )
    pincode_prefix = serializers.RegexField(
        regex=r"^\d{1,10}$",
        required=False,
        max_length=10,
        trim_whitespace=True,
        error_messages={
            "invalid": "Enter a numeric pincode prefix.",
        },
    )


class StateSerializer(serializers.ModelSerializer):
    class Meta:
        model = State
        fields = ("id", "name", "slug", "code")


class CitySerializer(serializers.ModelSerializer):
    state = StateSerializer(read_only=True)

    class Meta:
        model = City
        fields = ("id", "name", "slug", "tier", "pincode_prefixes", "state")


class AddressSerializer(serializers.ModelSerializer):
    city = CitySerializer(read_only=True)
    city_id = serializers.PrimaryKeyRelatedField(
        queryset=City.objects.all(),
        source="city",
        write_only=True,
    )
    label = serializers.CharField(read_only=True)
    full_address = serializers.CharField(read_only=True)

    class Meta:
        model = Address
        fields = (
            "id",
            "address_type",
            "custom_label",
            "label",
            "recipient_name",
            "phone",
            "address_line1",
            "address_line2",
            "landmark",
            "city",
            "city_id",
            "postal_code",
            "latitude",
            "longitude",
            "is_default",
            "is_active",
            "full_address",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        data = {}
        if self.instance is not None:
            for field in self.Meta.model._meta.fields:
                data[field.name] = getattr(self.instance, field.name)
        data.update(attrs)
        if "user" not in data and self.context.get("user") is not None:
            data["user"] = self.context["user"]

        address = Address(**data)
        address.clean()
        return attrs
