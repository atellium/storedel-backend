from datetime import datetime, timedelta

from rest_framework import serializers
from django.utils import timezone

from products.models import ProductCategory
from stores.models import SavedStore, Store, StoreSettings


DAY_KEYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)

DAY_LABELS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def get_store_current_status(store_hours):
    now = timezone.localtime()
    today_index = now.weekday()
    today_slots = get_day_slots(store_hours, today_index)

    for slot in today_slots:
        open_time = parse_time_value(slot.get("open"))
        close_time = parse_time_value(slot.get("close"))
        if not open_time or not close_time:
            continue

        open_at = timezone.make_aware(
            datetime.combine(now.date(), open_time),
            timezone.get_current_timezone(),
        )
        close_at = timezone.make_aware(
            datetime.combine(now.date(), close_time),
            timezone.get_current_timezone(),
        )
        if close_at <= open_at:
            close_at += timedelta(days=1)

        if open_at <= now < close_at:
            minutes_to_close = (close_at - now).total_seconds() / 60
            text = "Closing Soon" if minutes_to_close <= 30 else "Open"
            return {
                "text": text,
                "next": f"until {format_time(close_at)}",
            }

        if now < open_at:
            return {
                "text": "Closed",
                "next": f"Opens today at {format_time(open_at)}",
            }

    next_opening = find_next_opening(store_hours, now, today_index)
    if next_opening is None:
        return {"text": "Closed", "next": ""}

    next_day_index, open_at = next_opening
    if next_day_index == today_index:
        next_text = f"Opens today at {format_time(open_at)}"
    else:
        next_text = f"Open {DAY_LABELS[next_day_index]} at {format_time(open_at)}"

    return {"text": "Closed", "next": next_text}


def get_delivery_status(store_settings):
    now = timezone.localtime()
    status = {
        "pickup": get_disable_till_delivery_status(
            is_enabled=store_settings.is_pickup_enabled,
            disable_till=store_settings.pickup_disable_till,
            now=now,
        ),
        "express_delivery": get_disable_till_delivery_status(
            is_enabled=store_settings.is_express_delivery_enabled,
            disable_till=store_settings.express_delivery_disable_till,
            now=now,
        ),
        "scheduled_delivery": get_scheduled_delivery_status(
            is_enabled=store_settings.is_scheduled_delivery_enabled,
            disable_till=store_settings.scheduled_delivery_disable_till,
            slots_json=store_settings.scheduled_delivery_slots,
            now=now,
        ),
    }
    return status


def get_disable_till_delivery_status(*, is_enabled, disable_till, now):
    result = {
        "is_enabled": is_enabled,
        "is_available": bool(is_enabled),
        "next_time": None,
    }

    if not is_enabled:
        return result

    if disable_till and now < disable_till:
        result["is_available"] = False
        result["next_time"] = format_datetime_value(disable_till)

    return result


def get_scheduled_delivery_status(*, is_enabled, disable_till, slots_json, now):
    result = {
        "is_enabled": is_enabled,
        "next_delivery_by": None,
    }

    if not is_enabled:
        return result

    if disable_till and now < disable_till:
        return result

    next_slot = find_next_slot(slots_json, now)
    if next_slot is not None:
        result["next_delivery_by"] = format_datetime_value(next_slot["end_at"])

    return result


def format_datetime_value(value):
    return serializers.DateTimeField().to_representation(value)


def find_next_slot(slots_json, after):
    for day_offset in range(8):
        check_date = after.date() + timedelta(days=day_offset)
        day_index = check_date.weekday()
        day_slots = get_slots_for_day(slots_json, check_date, day_index)
        for slot in day_slots:
            if after < slot["start_at"]:
                return slot
    return None


def get_slots_for_day(slots_json, slot_date, day_index):
    slots = []
    for slot in get_day_slots(slots_json, day_index):
        start_time = parse_slot_time(slot, ("open", "start", "from", "start_time"))
        end_time = parse_slot_time(slot, ("close", "end", "to", "end_time", "delivery_end"))
        if not start_time or not end_time:
            continue

        start_at = timezone.make_aware(
            datetime.combine(slot_date, start_time),
            timezone.get_current_timezone(),
        )
        end_at = timezone.make_aware(
            datetime.combine(slot_date, end_time),
            timezone.get_current_timezone(),
        )
        if end_at <= start_at:
            end_at += timedelta(days=1)

        slots.append({"start_at": start_at, "end_at": end_at})

    return sorted(slots, key=lambda slot: slot["start_at"])


def parse_slot_time(slot, keys):
    for key in keys:
        time_value = parse_time_value(slot.get(key))
        if time_value:
            return time_value
    return None


def find_next_opening(store_hours, now, today_index):
    for day_offset in range(1, 8):
        day_index = (today_index + day_offset) % 7
        slots = get_day_slots(store_hours, day_index)
        if not slots:
            continue

        open_time = parse_time_value(slots[0].get("open"))
        if not open_time:
            continue

        open_date = now.date() + timedelta(days=day_offset)
        open_at = timezone.make_aware(
            datetime.combine(open_date, open_time),
            timezone.get_current_timezone(),
        )
        return day_index, open_at

    return None


def get_day_slots(store_hours, day_index):
    if not isinstance(store_hours, dict):
        return []

    day_values = (
        DAY_KEYS[day_index],
        DAY_KEYS[day_index].title(),
        DAY_KEYS[day_index][:3],
        DAY_KEYS[day_index][:3].title(),
        str(day_index),
        str(day_index + 1),
    )
    value = next(
        (store_hours[key] for key in day_values if key in store_hours),
        None,
    )
    if not value:
        return []

    if isinstance(value, dict) and value.get("closed"):
        return []

    if isinstance(value, dict) and isinstance(value.get("slots"), list):
        value = value["slots"]

    if isinstance(value, dict):
        value = [value]

    if not isinstance(value, list):
        return []

    slots = []
    for item in value:
        if isinstance(item, dict) and not item.get("closed"):
            slots.append(item)
    return slots


def parse_time_value(value):
    if not isinstance(value, str):
        return None

    value = value.strip()
    for time_format in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I%p"):
        try:
            return datetime.strptime(value.upper(), time_format).time()
        except ValueError:
            continue

    return None


def format_time(value):
    return timezone.localtime(value).strftime("%I:%M%p").lstrip("0").replace(":00", "")


class StoreProductCategorySerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ProductCategory
        fields = (
            "id",
            "name",
            "slug",
            "aliases",
            "image_url",
            "sort_order",
        )

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        url = obj.image.url
        return request.build_absolute_uri(url) if request and url.startswith("/") else url


class StoreListQuerySerializer(serializers.Serializer):
    search = serializers.CharField(
        required=False,
        max_length=180,
        trim_whitespace=True,
        allow_blank=False,
    )
    pincode = serializers.CharField(
        required=False,
        max_length=6,
        trim_whitespace=True,
        allow_blank=False,
    )
    city = serializers.SlugField(required=False, max_length=100)
    locality = serializers.CharField(
        required=False,
        max_length=100,
        trim_whitespace=True,
        allow_blank=False,
    )
    geohash = serializers.CharField(
        required=False,
        max_length=12,
        trim_whitespace=True,
        allow_blank=False,
    )
    is_active = serializers.BooleanField(required=False)
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)


class NearbyStoreListQuerySerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lng = serializers.FloatField(min_value=-180, max_value=180)
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100)


class StoreDetailSerializer(serializers.ModelSerializer):
    city = serializers.SerializerMethodField()
    cover_image = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()
    category_grid = serializers.SerializerMethodField()
    current_status = serializers.SerializerMethodField()
    delivery_status = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = (
            "id",
            "name",
            "title",
            "slug",
            "host_name",
            "address",
            "locality",
            "city",
            "pincode",
            "latitude",
            "longitude",
            "geohash",
            "phone",
            "whatsapp",
            "email",
            "website",
            "cover_image",
            "categories",
            "category_grid",
            "store_hours",
            "current_status",
            "delivery_status",
            "is_active",
            "published_at",
            "created_at",
            "updated_at",
        )

    def get_city(self, obj):
        if obj.city is None:
            return None
        return {
            "id": obj.city_id,
            "name": obj.city.name,
            "slug": obj.city.slug,
            "state": {
                "id": obj.city.state_id,
                "name": obj.city.state.name,
                "slug": obj.city.state.slug,
                "code": obj.city.state.code,
            },
        }

    def get_cover_image(self, obj):
        if not obj.cover_image:
            return None
        request = self.context.get("request")
        url = obj.cover_image.url
        return request.build_absolute_uri(url) if request else url

    def get_categories(self, obj):
        categories = (
            ProductCategory.objects.filter(
                products__store=obj,
                products__is_active=True,
                is_active=True,
            )
            .distinct()
            .order_by("sort_order", "name", "id")
        )
        return StoreProductCategorySerializer(
            categories,
            many=True,
            context=self.context,
        ).data

    def get_category_grid(self, obj):
        available_categories = (
            ProductCategory.objects.filter(
                products__store=obj,
                products__is_active=True,
                is_active=True,
            )
            .select_related("parent", "parent__parent")
            .distinct()
        )

        root_ids = set()
        child_ids_by_root = {}
        for category in available_categories:
            if category.parent_id is None:
                root_ids.add(category.id)
                continue

            if category.parent.parent_id is None:
                root = category.parent
                child = category
            else:
                root = category.parent.parent
                child = category.parent

            if not root.is_active or not child.is_active:
                continue

            root_ids.add(root.id)
            child_ids_by_root.setdefault(root.id, set()).add(child.id)

        if not root_ids:
            return []

        child_ids = {
            child_id
            for ids in child_ids_by_root.values()
            for child_id in ids
        }
        children = ProductCategory.objects.filter(
            parent_id__in=root_ids,
            id__in=child_ids,
            is_active=True,
        ).order_by("sort_order", "name", "id")

        children_by_root = {}
        for child in children:
            children_by_root.setdefault(child.parent_id, []).append(child)

        grid = []
        roots = ProductCategory.objects.filter(
            id__in=root_ids,
            is_active=True,
            parent__isnull=True,
        ).order_by("sort_order", "name", "id")
        for root in roots:
            root_data = StoreProductCategorySerializer(
                root,
                context=self.context,
            ).data
            root_data["children"] = StoreProductCategorySerializer(
                children_by_root.get(root.id, []),
                many=True,
                context=self.context,
            ).data
            grid.append(root_data)

        return grid

    def get_current_status(self, obj):
        return get_store_current_status(obj.store_hours)

    def get_delivery_status(self, obj):
        try:
            store_settings = obj.settings
        except Store.settings.RelatedObjectDoesNotExist:
            return None

        return get_delivery_status(store_settings)


class StoreListSerializer(StoreDetailSerializer):
    class Meta(StoreDetailSerializer.Meta):
        fields = (
            "id",
            "name",
            "title",
            "slug",
            "host_name",
            "locality",
            "city",
            "pincode",
            "latitude",
            "longitude",
            "cover_image",
            "is_active",
            "published_at",
            "updated_at",
        )


class NearbyStoreListSerializer(StoreListSerializer):
    distance_km = serializers.FloatField(read_only=True)

    class Meta(StoreListSerializer.Meta):
        fields = StoreListSerializer.Meta.fields + ("distance_km",)


class SavedStoreSerializer(serializers.ModelSerializer):
    store = StoreListSerializer(read_only=True)
    saved_at = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = SavedStore
        fields = (
            "id",
            "store",
            "saved_at",
        )


class StoreSettingsSerializer(serializers.ModelSerializer):
    accepts_pickup = serializers.BooleanField(read_only=True)
    accepts_express_delivery = serializers.BooleanField(read_only=True)
    accepts_scheduled_delivery = serializers.BooleanField(read_only=True)
    is_pickup_temporarily_disabled = serializers.BooleanField(read_only=True)
    is_express_delivery_temporarily_disabled = serializers.BooleanField(read_only=True)
    is_scheduled_delivery_temporarily_disabled = serializers.BooleanField(read_only=True)
    has_available_fulfillment_method = serializers.BooleanField(read_only=True)

    class Meta:
        model = StoreSettings
        fields = (
            "id",
            "store",
            "is_open",
            "is_pickup_enabled",
            "is_express_delivery_enabled",
            "is_scheduled_delivery_enabled",
            "scheduled_delivery_range_km",
            "scheduled_min_order_amount",
            "scheduled_delivery_charge",
            "scheduled_delivery_slots",
            "scheduled_delivery_disable_till",
            "express_delivery_range_km",
            "express_min_order_amount",
            "express_delivery_charge",
            "express_delivery_disable_till",
            "express_min_delivery_minutes",
            "express_max_delivery_minutes",
            "pickup_min_order_amount",
            "pickup_disable_till",
            "pickup_min_preparation_minutes",
            "pickup_max_preparation_minutes",
            "is_pickup_temporarily_disabled",
            "is_express_delivery_temporarily_disabled",
            "is_scheduled_delivery_temporarily_disabled",
            "accepts_pickup",
            "accepts_express_delivery",
            "accepts_scheduled_delivery",
            "has_available_fulfillment_method",
        )
        read_only_fields = fields


class StoreSettingsUpdateSerializer(StoreSettingsSerializer):
    class Meta(StoreSettingsSerializer.Meta):
        read_only_fields = (
            "id",
            "store",
            "accepts_pickup",
            "accepts_express_delivery",
            "accepts_scheduled_delivery",
            "is_pickup_temporarily_disabled",
            "is_express_delivery_temporarily_disabled",
            "is_scheduled_delivery_temporarily_disabled",
            "has_available_fulfillment_method",
        )


class MyStoreDetailSerializer(StoreDetailSerializer):
    total_products = serializers.IntegerField(read_only=True)
    total_orders = serializers.IntegerField(read_only=True)

    class Meta(StoreDetailSerializer.Meta):
        fields = StoreDetailSerializer.Meta.fields + (
            "total_products",
            "total_orders",
        )
