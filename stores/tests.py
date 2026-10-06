from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase

from stores.models import SavedStore, Store, StoreSettings
from stores.serializers import StoreDetailSerializer


class StoreListTests(APITestCase):
    def test_store_list_returns_pagination_details_without_page_urls(self):
        for index in range(3):
            Store.objects.create(
                name=f"Store {index}",
                title=f"Store Title {index}",
                address=f"{index} Market Road",
                is_active=True,
            )

        response = self.client.get(
            reverse("stores:store-list"),
            {"page": 2, "page_size": 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("next", response.data)
        self.assertNotIn("previous", response.data)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "Store Title 2")
        self.assertEqual(
            response.data["pagination"],
            {
                "page": 2,
                "page_size": 2,
                "total_items": 3,
                "total_pages": 2,
                "has_next": False,
                "has_previous": True,
                "next_page": None,
                "previous_page": 1,
            },
        )


class StoreDetailTests(APITestCase):
    def test_store_detail_returns_store_by_host_name(self):
        store = Store.objects.create(
            name="Host Store",
            title="Host Store Title",
            address="Main Road",
            host_name="host-store",
            is_active=True,
        )

        response = self.client.get(
            reverse(
                "stores:store-detail",
                kwargs={"store_slug": store.host_name},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"]["id"], str(store.id))
        self.assertEqual(response.data["result"]["host_name"], store.host_name)

    def test_store_detail_returns_store_by_dotted_host_name(self):
        store = Store.objects.create(
            name="Domain Store",
            address="Main Road",
            host_name="shop.example.com",
            is_active=True,
        )

        response = self.client.get("/api/stores/shop.example.com/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"]["id"], str(store.id))
        self.assertEqual(response.data["result"]["host_name"], store.host_name)

    def test_store_detail_still_returns_store_by_slug(self):
        store = Store.objects.create(
            name="Slug Store",
            address="Main Road",
            is_active=True,
        )

        response = self.client.get(
            reverse(
                "stores:store-detail",
                kwargs={"store_slug": store.slug},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["result"]["id"], str(store.id))

    def test_store_detail_by_host_name_requires_active_store(self):
        store = Store.objects.create(
            name="Inactive Host Store",
            address="Main Road",
            host_name="inactive-host",
            is_active=False,
        )

        response = self.client.get(
            reverse(
                "stores:store-detail",
                kwargs={"store_slug": store.host_name},
            )
        )

        self.assertEqual(response.status_code, 404)


class NearbyStoreListTests(APITestCase):
    def test_nearby_store_list_returns_matching_geohash_stores_by_distance(self):
        near_store = Store.objects.create(
            name="Near Store",
            address="Near Road",
            latitude=12.9717,
            longitude=77.5947,
            is_active=True,
        )
        far_store = Store.objects.create(
            name="Far Store",
            address="Far Road",
            latitude=12.979,
            longitude=77.599,
            is_active=True,
        )
        inactive_store = Store.objects.create(
            name="Inactive Store",
            address="Inactive Road",
            latitude=12.9718,
            longitude=77.5948,
            is_active=False,
        )
        other_geohash_store = Store.objects.create(
            name="Other City Store",
            address="Other Road",
            latitude=28.6139,
            longitude=77.209,
            is_active=True,
        )

        response = self.client.get(
            reverse("stores:nearby-store-list"),
            {"lat": 12.9716, "lng": 77.5946},
        )

        self.assertEqual(response.status_code, 200)
        result_ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(result_ids, [str(near_store.id), str(far_store.id)])
        self.assertNotIn(str(inactive_store.id), result_ids)
        self.assertNotIn(str(other_geohash_store.id), result_ids)
        self.assertLess(
            response.data["results"][0]["distance_km"],
            response.data["results"][1]["distance_km"],
        )

    def test_nearby_store_list_requires_valid_coordinates(self):
        response = self.client.get(
            reverse("stores:nearby-store-list"),
            {"lat": 100, "lng": 77.5946},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("lat", response.data)


class SavedStoreTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(phone="+919876543210")
        self.other_user = user_model.objects.create_user(phone="+919876543211")
        self.store = Store.objects.create(
            name="Saved Store",
            address="Main Road",
            is_active=True,
        )
        self.other_store = Store.objects.create(
            name="Other Store",
            address="Other Road",
            is_active=True,
        )

    def test_saved_store_list_requires_authentication(self):
        response = self.client.get(reverse("stores:saved-store-list"))

        self.assertIn(response.status_code, (401, 403))

    def test_user_can_save_store_once(self):
        self.client.force_authenticate(self.user)
        url = reverse(
            "stores:saved-store-detail",
            kwargs={"store_slug": self.store.slug},
        )

        first_response = self.client.post(url)
        second_response = self.client.post(url)

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(
            SavedStore.objects.filter(user=self.user, store=self.store).count(),
            1,
        )
        self.assertTrue(second_response.data["saved"])

    def test_user_can_list_saved_stores(self):
        SavedStore.objects.create(user=self.user, store=self.store)
        SavedStore.objects.create(user=self.other_user, store=self.other_store)
        self.client.force_authenticate(self.user)

        response = self.client.get(reverse("stores:saved-store-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["store"]["slug"], self.store.slug)
        self.assertIn("saved_at", response.data["results"][0])

    def test_user_can_remove_saved_store(self):
        SavedStore.objects.create(user=self.user, store=self.store)
        self.client.force_authenticate(self.user)
        url = reverse(
            "stores:saved-store-detail",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            SavedStore.objects.filter(user=self.user, store=self.store).exists()
        )

    def test_cannot_save_inactive_store(self):
        self.store.is_active = False
        self.store.save(update_fields=["is_active"])
        self.client.force_authenticate(self.user)
        url = reverse(
            "stores:saved-store-detail",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            SavedStore.objects.filter(user=self.user, store=self.store).exists()
        )


class StoreSettingsDetailTests(APITestCase):
    def setUp(self):
        self.store = Store.objects.create(
            name="Settings Store",
            address="Main Road",
            is_active=True,
        )
        self.settings = StoreSettings.objects.create(
            store=self.store,
            express_delivery_range_km=5,
            scheduled_delivery_range_km=6,
        )

    def test_store_settings_detail_returns_settings_by_store_slug(self):
        response = self.client.get(
            reverse(
                "stores:store-settings-detail",
                kwargs={"store_slug": self.store.slug},
            )
        )

        self.assertEqual(response.status_code, 200)
        result = response.data["result"]
        self.assertEqual(result["id"], str(self.settings.id))
        self.assertEqual(result["store"], self.store.id)
        self.assertTrue(result["is_open"])
        self.assertTrue(result["accepts_pickup"])
        self.assertTrue(result["accepts_express_delivery"])
        self.assertTrue(result["accepts_scheduled_delivery"])
        self.assertFalse(result["is_pickup_temporarily_disabled"])
        self.assertFalse(result["is_express_delivery_temporarily_disabled"])
        self.assertFalse(result["is_scheduled_delivery_temporarily_disabled"])
        self.assertTrue(result["has_available_fulfillment_method"])
        self.assertIn("pickup_disable_till", result)
        self.assertIn("express_delivery_disable_till", result)
        self.assertIn("scheduled_delivery_disable_till", result)

    def test_store_settings_detail_requires_active_store(self):
        self.store.is_active = False
        self.store.save(update_fields=["is_active"])

        response = self.client.get(
            reverse(
                "stores:store-settings-detail",
                kwargs={"store_slug": self.store.slug},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_store_settings_detail_returns_404_without_settings(self):
        store = Store.objects.create(
            name="No Settings Store",
            address="Main Road",
            is_active=True,
        )

        response = self.client.get(
            reverse(
                "stores:store-settings-detail",
                kwargs={"store_slug": store.slug},
            )
        )

        self.assertEqual(response.status_code, 404)


class StoreSettingsUpdateTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(phone="+919876543212")
        self.other_user = user_model.objects.create_user(phone="+919876543213")
        self.store = Store.objects.create(
            owner=self.user,
            name="Owned Settings Store",
            address="Main Road",
            is_active=True,
        )
        self.settings = StoreSettings.objects.create(
            store=self.store,
            express_delivery_range_km=5,
            scheduled_delivery_range_km=6,
        )
        self.url = reverse(
            "stores:my-store-settings-update",
            kwargs={"store_slug": self.store.slug},
        )

    def test_owner_can_patch_store_settings_disable_dates(self):
        self.client.force_authenticate(self.user)
        disable_till = timezone.now() + timedelta(hours=2)

        response = self.client.patch(
            self.url,
            {
                "pickup_disable_till": disable_till.isoformat(),
                "express_delivery_disable_till": disable_till.isoformat(),
                "scheduled_delivery_disable_till": disable_till.isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        result = response.data["result"]
        self.assertTrue(result["is_pickup_temporarily_disabled"])
        self.assertTrue(result["is_express_delivery_temporarily_disabled"])
        self.assertTrue(result["is_scheduled_delivery_temporarily_disabled"])
        self.assertFalse(result["accepts_pickup"])
        self.assertFalse(result["accepts_express_delivery"])
        self.assertFalse(result["accepts_scheduled_delivery"])
        self.assertFalse(result["has_available_fulfillment_method"])

    def test_owner_can_get_store_settings(self):
        self.client.force_authenticate(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        result = response.data["result"]
        self.assertEqual(result["id"], str(self.settings.id))
        self.assertEqual(result["store"], self.store.id)

    def test_owner_get_creates_missing_store_settings(self):
        self.settings.delete()
        self.client.force_authenticate(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        result = response.data["result"]
        self.assertEqual(result["store"], self.store.id)
        self.assertTrue(result["is_pickup_enabled"])
        self.assertFalse(result["is_express_delivery_enabled"])
        self.assertFalse(result["is_scheduled_delivery_enabled"])
        self.assertTrue(StoreSettings.objects.filter(store=self.store).exists())

    def test_patch_ignores_read_only_availability_fields(self):
        self.client.force_authenticate(self.user)

        response = self.client.patch(
            self.url,
            {
                "accepts_pickup": False,
                "has_available_fulfillment_method": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        result = response.data["result"]
        self.assertTrue(result["accepts_pickup"])
        self.assertTrue(result["has_available_fulfillment_method"])

    def test_other_user_cannot_patch_store_settings(self):
        self.client.force_authenticate(self.other_user)

        response = self.client.patch(
            self.url,
            {"is_open": False},
            format="json",
        )

        self.assertEqual(response.status_code, 404)


class StoreCurrentStatusTests(APITestCase):
    def serialize_status(self, store_hours, now):
        store = Store.objects.create(
            name="Status Store",
            address="Main Road",
            store_hours=store_hours,
        )
        aware_now = timezone.make_aware(now, timezone.get_current_timezone())
        with patch("stores.serializers.timezone.now", return_value=aware_now):
            return StoreDetailSerializer(store).data["current_status"]

    def test_store_detail_current_status_open(self):
        status = self.serialize_status(
            {"thursday": {"open": "08:00", "close": "20:00"}},
            datetime(2026, 9, 24, 12, 0),
        )

        self.assertEqual(
            status,
            {
                "text": "Open",
                "next": "until 8PM",
            },
        )

    def test_store_detail_current_status_closing_soon(self):
        status = self.serialize_status(
            {"thursday": {"open": "08:00", "close": "20:00"}},
            datetime(2026, 9, 24, 19, 45),
        )

        self.assertEqual(status["text"], "Closing Soon")
        self.assertEqual(status["next"], "until 8PM")

    def test_store_detail_current_status_opens_today(self):
        status = self.serialize_status(
            {"thursday": {"open": "08:00", "close": "20:00"}},
            datetime(2026, 9, 24, 7, 0),
        )

        self.assertEqual(
            status,
            {
                "text": "Closed",
                "next": "Opens today at 8AM",
            },
        )

    def test_store_detail_current_status_next_open_day(self):
        status = self.serialize_status(
            {"monday": {"open": "07:00", "close": "20:00"}},
            datetime(2026, 9, 24, 21, 0),
        )

        self.assertEqual(
            status,
            {
                "text": "Closed",
                "next": "Open Monday at 7AM",
            },
        )
