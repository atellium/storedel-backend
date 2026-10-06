from rest_framework import serializers

from notifications.models import DeviceToken


class DeviceTokenRegisterSerializer(serializers.Serializer):
    device_id = serializers.CharField(max_length=255, trim_whitespace=True)
    token = serializers.CharField(trim_whitespace=True)
    platform = serializers.ChoiceField(choices=DeviceToken.Platform.choices)
    browser = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        trim_whitespace=True,
    )
    os = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        trim_whitespace=True,
    )
    app_version = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=50,
        trim_whitespace=True,
    )

    def validate_device_id(self, value):
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value

    def validate_token(self, value):
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value


class DeviceTokenUnregisterSerializer(serializers.Serializer):
    device_id = serializers.CharField(max_length=255, trim_whitespace=True)

    def validate_device_id(self, value):
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = (
            "id",
            "device_id",
            "token",
            "platform",
            "browser",
            "os",
            "app_version",
            "is_active",
            "failure_count",
            "last_seen_at",
        )
        read_only_fields = fields
