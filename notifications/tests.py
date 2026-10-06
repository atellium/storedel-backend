from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from notifications.models import DeviceToken
from notifications.tasks import send_store_owner_order_placed_notification
from orders.models import Order
from stores.models import Store


class DeviceTokenAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="+919876543210")
        self.other_user = User.objects.create_user(phone="+919876543211")
        self.register_url = reverse("notifications:device-token-register")
        self.unregister_url = reverse("notifications:device-token-unregister")

    def authenticate(self, user=None):
        self.client.force_authenticate(user or self.user)

    def payload(self, **overrides):
        data = {
            "device_id": "device-1",
            "token": "fcm-token-1",
            "platform": DeviceToken.Platform.ANDROID,
            "browser": "Chrome",
            "os": "Android",
            "app_version": "1.0.0",
        }
        data.update(overrides)
        return data

    def test_register_requires_authentication(self):
        response = self.client.post(self.register_url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_new_registration_creates_active_token(self):
        self.authenticate()

        response = self.client.post(self.register_url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        device_token = DeviceToken.objects.get()
        self.assertEqual(device_token.user, self.user)
        self.assertEqual(device_token.device_id, "device-1")
        self.assertEqual(device_token.token, "fcm-token-1")
        self.assertTrue(device_token.is_active)
        self.assertEqual(device_token.failure_count, 0)
        self.assertIsNotNone(device_token.last_seen_at)

    def test_repeated_registration_updates_existing_token(self):
        self.authenticate()
        first = self.client.post(self.register_url, self.payload(), format="json")
        token_id = first.data["device_token"]["id"]

        response = self.client.post(
            self.register_url,
            self.payload(browser="Firefox", app_version="1.0.1"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(DeviceToken.objects.count(), 1)
        device_token = DeviceToken.objects.get()
        self.assertEqual(str(device_token.id), token_id)
        self.assertEqual(device_token.browser, "Firefox")
        self.assertEqual(device_token.app_version, "1.0.1")

    def test_token_rotation_updates_same_user_device(self):
        self.authenticate()
        DeviceToken.objects.create(
            user=self.user,
            device_id="device-1",
            token="old-token",
            platform=DeviceToken.Platform.ANDROID,
            failure_count=3,
        )

        response = self.client.post(
            self.register_url,
            self.payload(token="new-token"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(DeviceToken.objects.count(), 1)
        device_token = DeviceToken.objects.get()
        self.assertEqual(device_token.token, "new-token")
        self.assertEqual(device_token.failure_count, 0)
        self.assertTrue(device_token.is_active)

    def test_reactivation_updates_inactive_record(self):
        self.authenticate()
        old_seen_at = timezone.now()
        DeviceToken.objects.create(
            user=self.user,
            device_id="device-1",
            token="fcm-token-1",
            platform=DeviceToken.Platform.ANDROID,
            is_active=False,
            failure_count=2,
            last_seen_at=old_seen_at,
        )

        response = self.client.post(self.register_url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        device_token = DeviceToken.objects.get()
        self.assertTrue(device_token.is_active)
        self.assertEqual(device_token.failure_count, 0)
        self.assertGreater(device_token.last_seen_at, old_seen_at)

    def test_existing_token_for_another_user_is_attached_to_current_user(self):
        self.authenticate()
        DeviceToken.objects.create(
            user=self.other_user,
            device_id="other-device",
            token="fcm-token-1",
            platform=DeviceToken.Platform.IOS,
        )

        response = self.client.post(
            self.register_url,
            self.payload(platform=DeviceToken.Platform.WEB),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(DeviceToken.objects.count(), 1)
        device_token = DeviceToken.objects.get()
        self.assertEqual(device_token.user, self.user)
        self.assertEqual(device_token.device_id, "device-1")
        self.assertEqual(device_token.platform, DeviceToken.Platform.WEB)

    def test_unregister_deactivates_current_user_device_only(self):
        self.authenticate()
        current = DeviceToken.objects.create(
            user=self.user,
            device_id="device-1",
            token="fcm-token-1",
            platform=DeviceToken.Platform.ANDROID,
        )
        other = DeviceToken.objects.create(
            user=self.other_user,
            device_id="device-1",
            token="other-token",
            platform=DeviceToken.Platform.ANDROID,
        )

        response = self.client.post(
            self.unregister_url,
            {"device_id": "device-1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        current.refresh_from_db()
        other.refresh_from_db()
        self.assertFalse(current.is_active)
        self.assertTrue(other.is_active)

    def test_unregister_does_not_delete_all_user_tokens(self):
        self.authenticate()
        DeviceToken.objects.create(
            user=self.user,
            device_id="device-1",
            token="fcm-token-1",
            platform=DeviceToken.Platform.ANDROID,
        )
        second = DeviceToken.objects.create(
            user=self.user,
            device_id="device-2",
            token="fcm-token-2",
            platform=DeviceToken.Platform.IOS,
        )

        response = self.client.post(
            self.unregister_url,
            {"device_id": "device-1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(DeviceToken.objects.count(), 2)
        second.refresh_from_db()
        self.assertTrue(second.is_active)

    def test_invalid_payload_is_rejected(self):
        self.authenticate()

        response = self.client.post(
            self.register_url,
            {"device_id": "", "token": "", "platform": "desktop"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("device_id", response.data)
        self.assertIn("token", response.data)
        self.assertIn("platform", response.data)


class StoreOwnerOrderPlacedNotificationTaskTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(phone="+919876543210")
        self.customer = User.objects.create_user(phone="+919876543211")
        self.store = Store.objects.create(
            owner=self.owner,
            name="Owner Store",
            code="OWN",
            address="Main Road",
        )
        self.order = Order.objects.create(
            user=self.customer,
            store=self.store,
            subtotal=100,
            total_amount=485,
            fullfillment_type=Order.FullfillmentType.EXPRESS_DELIVERY,
        )

    @override_settings(SITE_URL="https://dukanik.example")
    @patch("notifications.tasks.send_push_notification", return_value="message-id")
    def test_task_sends_to_active_store_owner_tokens(self, send_push_notification):
        owner_token = DeviceToken.objects.create(
            user=self.owner,
            device_id="owner-device",
            token="owner-token",
            platform=DeviceToken.Platform.ANDROID,
            failure_count=2,
        )
        inactive_token = DeviceToken.objects.create(
            user=self.owner,
            device_id="inactive-device",
            token="inactive-token",
            platform=DeviceToken.Platform.IOS,
            is_active=False,
        )
        other_user = User.objects.create_user(phone="+919876543212")
        DeviceToken.objects.create(
            user=other_user,
            device_id="other-device",
            token="other-token",
            platform=DeviceToken.Platform.WEB,
        )

        result = send_store_owner_order_placed_notification(str(self.order.id))

        self.assertEqual(result, {"sent": 1, "failed": 0, "skipped": 0})
        send_push_notification.assert_called_once()
        self.assertEqual(send_push_notification.call_args.kwargs["token"], "owner-token")
        self.assertEqual(
            send_push_notification.call_args.kwargs["title"],
            "New Order Received! 🛍️",
        )
        self.assertEqual(
            send_push_notification.call_args.kwargs["body"],
            f"₹485 • Express Delivery • Order #{self.order.order_number}",
        )
        self.assertEqual(
            send_push_notification.call_args.kwargs["data"]["type"],
            "order_placed",
        )
        self.assertEqual(
            send_push_notification.call_args.kwargs["data"]["url"],
            (
                "https://dukanik.example/"
                f"{self.store.slug}/manage/orders/{self.order.order_number}"
            ),
        )
        owner_token.refresh_from_db()
        inactive_token.refresh_from_db()
        self.assertEqual(owner_token.failure_count, 0)
        self.assertIsNotNone(owner_token.last_notification_at)
        self.assertIsNone(inactive_token.last_notification_at)

    @patch("notifications.tasks.send_push_notification", return_value=None)
    def test_task_increments_failure_count_when_send_fails(self, send_push_notification):
        device_token = DeviceToken.objects.create(
            user=self.owner,
            device_id="owner-device",
            token="owner-token",
            platform=DeviceToken.Platform.ANDROID,
            failure_count=1,
        )

        result = send_store_owner_order_placed_notification(str(self.order.id))

        self.assertEqual(result, {"sent": 0, "failed": 1, "skipped": 0})
        send_push_notification.assert_called_once()
        device_token.refresh_from_db()
        self.assertEqual(device_token.failure_count, 2)
        self.assertIsNone(device_token.last_notification_at)
