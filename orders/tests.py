from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from carts.models import Cart, CartItem
from orders.models import Order, OrderItem
from products.models import Product, ProductVariant
from stores.models import Store


class MyStoreOrderTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            phone="+919876543210",
            full_name="Store Owner",
        )
        self.other_owner = user_model.objects.create_user(phone="+919876543211")
        self.customer = user_model.objects.create_user(
            phone="+919876543212",
            full_name="Test Customer",
            email="customer@example.com",
        )
        self.store = Store.objects.create(
            owner=self.owner,
            name="Owner Store",
            code="CHA",
            address="Main Road",
        )
        self.other_store = Store.objects.create(
            owner=self.other_owner,
            name="Other Store",
            code="OTH",
            address="Other Road",
        )
        self.product = Product.objects.create(
            store=self.store,
            name="Test Product",
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            value=None,
            unit=ProductVariant.Unit.PACK,
            pack_count=1,
            price=50,
        )
        self.order = Order.objects.create(
            user=self.customer,
            store=self.store,
            subtotal=100,
            total_amount=100,
            customer_note="Please pack carefully",
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            variant=self.variant,
            selection_type=OrderItem.SelectionType.VARIANT,
            product_public_id=self.product.public_id,
            product_name=self.product.name,
            variant_name=self.variant.name,
            measurement_type=self.product.measurement_type,
            measurement_value=self.variant.value,
            unit=self.variant.unit,
            pack_count=self.variant.pack_count,
            quantity=2,
            unit_price=50,
            line_total=100,
        )

    def test_order_number_uses_store_code_random_code_and_daily_serial(self):
        with patch("orders.models.secrets.choice", side_effect=list("ABCXYZ")):
            first_order = Order.objects.create(
                user=self.customer,
                store=self.store,
                subtotal=50,
                total_amount=50,
            )
            second_order = Order.objects.create(
                user=self.customer,
                store=self.store,
                subtotal=75,
                total_amount=75,
            )

        self.assertEqual(first_order.order_number, "CHAABC0002")
        self.assertEqual(second_order.order_number, "CHAXYZ0003")
        self.assertEqual(len(second_order.order_number), 10)
        self.assertRegex(second_order.order_number, r"^CHA[A-Z0-9]{3}\d{4}$")

    def test_owner_can_list_store_orders(self):
        self.client.force_authenticate(self.owner)
        url = reverse(
            "orders:my-store-order-list",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.order.pk))
        self.assertEqual(response.data["results"][0]["items"][0]["is_ready"], False)
        self.assertEqual(
            response.data["results"][0]["customer"]["phone"],
            self.customer.phone,
        )

    def test_owner_can_list_store_customers(self):
        second_customer = get_user_model().objects.create_user(
            phone="+919876543213",
            full_name="Second Customer",
            email="second@example.com",
        )
        Order.objects.create(
            user=self.customer,
            store=self.store,
            subtotal=50,
            total_amount=50,
        )
        Order.objects.create(
            user=second_customer,
            store=self.store,
            subtotal=75,
            total_amount=75,
        )
        Order.objects.create(
            user=second_customer,
            store=self.other_store,
            subtotal=200,
            total_amount=200,
        )
        self.client.force_authenticate(self.owner)
        url = reverse(
            "orders:my-store-customer-list",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        customers = {
            customer["id"]: customer
            for customer in response.data["results"]
        }
        self.assertEqual(customers[str(self.customer.id)]["order_count"], 2)
        self.assertEqual(customers[str(self.customer.id)]["total_amount"], 150)
        self.assertEqual(customers[str(second_customer.id)]["order_count"], 1)
        self.assertEqual(customers[str(second_customer.id)]["total_amount"], 75)

    def test_non_owner_cannot_list_store_customers(self):
        self.client.force_authenticate(self.other_owner)
        url = reverse(
            "orders:my-store-customer-list",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_non_owner_cannot_list_store_orders(self):
        self.client.force_authenticate(self.other_owner)
        url = reverse(
            "orders:my-store-order-list",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_customer_can_list_own_orders_for_store(self):
        other_order = Order.objects.create(
            user=self.customer,
            store=self.other_store,
            subtotal=50,
            total_amount=50,
        )
        OrderItem.objects.create(
            order=other_order,
            product_name="Other Product",
            selection_type=OrderItem.SelectionType.VARIANT,
            quantity=1,
            unit_price=50,
            line_total=50,
        )
        self.client.force_authenticate(self.customer)
        url = reverse(
            "orders:store-user-order-list",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.order.pk))
        self.assertEqual(
            response.data["results"][0]["store"]["slug"],
            self.store.slug,
        )

    def test_customer_store_order_list_only_returns_authenticated_users_orders(self):
        Order.objects.create(
            user=self.other_owner,
            store=self.store,
            subtotal=50,
            total_amount=50,
        )
        self.client.force_authenticate(self.customer)
        url = reverse(
            "orders:store-user-order-list",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.order.pk))

    def test_customer_can_filter_store_orders_by_status(self):
        Order.objects.create(
            user=self.customer,
            store=self.store,
            status=Order.Status.CANCELLED,
            subtotal=50,
            total_amount=50,
        )
        self.client.force_authenticate(self.customer)
        url = reverse(
            "orders:store-user-order-list",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.get(url, {"status": Order.Status.PLACED})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.order.pk))
        self.assertEqual(response.data["results"][0]["status"], Order.Status.PLACED)

    def test_customer_can_filter_store_orders_by_fullfillment_type(self):
        Order.objects.create(
            user=self.customer,
            store=self.store,
            fullfillment_type=Order.FullfillmentType.PICKUP,
            subtotal=50,
            total_amount=50,
        )
        self.client.force_authenticate(self.customer)
        url = reverse(
            "orders:store-user-order-list",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.get(
            url,
            {"fullfillment_type": Order.FullfillmentType.SCHEDULED_DELIVERY},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.order.pk))
        self.assertEqual(
            response.data["results"][0]["fullfillment_type"],
            Order.FullfillmentType.SCHEDULED_DELIVERY,
        )

    def test_owner_can_filter_store_orders_by_fullfillment_type(self):
        Order.objects.create(
            user=self.customer,
            store=self.store,
            fullfillment_type=Order.FullfillmentType.PICKUP,
            subtotal=50,
            total_amount=50,
        )
        self.client.force_authenticate(self.owner)
        url = reverse(
            "orders:my-store-order-list",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.get(
            url,
            {"fullfillment_type": Order.FullfillmentType.SCHEDULED_DELIVERY},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.order.pk))
        self.assertEqual(
            response.data["results"][0]["fullfillment_type"],
            Order.FullfillmentType.SCHEDULED_DELIVERY,
        )

    def test_owner_can_update_store_order_status(self):
        self.client.force_authenticate(self.owner)
        url = reverse(
            "orders:my-store-order-detail",
            kwargs={
                "store_slug": self.store.slug,
                "order_number": self.order.order_number,
            },
        )

        response = self.client.patch(
            url,
            {"status": Order.Status.ACCEPTED},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.ACCEPTED)
        self.assertEqual(response.data["order"]["status"], Order.Status.ACCEPTED)

    def test_owner_can_update_store_order_checkout_fields(self):
        self.order.delivery_fee = 25
        self.order.total_amount = 125
        self.order.save()
        self.client.force_authenticate(self.owner)
        url = reverse(
            "orders:my-store-order-detail",
            kwargs={
                "store_slug": self.store.slug,
                "order_number": self.order.order_number,
            },
        )

        response = self.client.patch(
            url,
            {
                "customer_note": "",
                "status": Order.Status.PREPARING,
                "fullfillment_type": Order.FullfillmentType.SCHEDULED_DELIVERY,
                "delivery_fee": 0,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.customer_note, "")
        self.assertEqual(self.order.status, Order.Status.PREPARING)
        self.assertEqual(
            self.order.fullfillment_type,
            Order.FullfillmentType.SCHEDULED_DELIVERY,
        )
        self.assertEqual(self.order.delivery_fee, 0)
        self.assertEqual(self.order.total_amount, 100)
        self.assertEqual(response.data["order"]["delivery_fee"], 0)
        self.assertEqual(response.data["order"]["total_amount"], 100)

    def test_owner_can_reject_store_order_with_reason(self):
        self.client.force_authenticate(self.owner)
        url = reverse(
            "orders:my-store-order-detail",
            kwargs={
                "store_slug": self.store.slug,
                "order_number": self.order.order_number,
            },
        )

        response = self.client.patch(
            url,
            {
                "status": Order.Status.REJECTED,
                "cancellation_reason": "Item is out of stock.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.REJECTED)
        self.assertEqual(self.order.cancellation_reason, "Item is out of stock.")

    def test_owner_can_update_order_item_ready_state(self):
        self.client.force_authenticate(self.owner)
        url = reverse(
            "orders:order-item-detail",
            kwargs={"item_id": self.order_item.id},
        )

        response = self.client.patch(
            url,
            {"is_ready": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.order_item.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.order_item.is_ready, True)
        self.assertEqual(self.order.status, Order.Status.READY)
        self.assertEqual(response.data["order"]["status"], Order.Status.READY)
        self.assertEqual(response.data["order"]["items"][0]["is_ready"], True)

    def test_owner_readying_one_item_does_not_ready_multi_item_order(self):
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            variant=self.variant,
            selection_type=OrderItem.SelectionType.VARIANT,
            product_public_id=self.product.public_id,
            product_name=self.product.name,
            variant_name=self.variant.name,
            measurement_type=self.product.measurement_type,
            measurement_value=self.variant.value,
            unit=self.variant.unit,
            pack_count=self.variant.pack_count,
            quantity=1,
            unit_price=50,
            line_total=50,
        )
        self.client.force_authenticate(self.owner)
        url = reverse(
            "orders:order-item-detail",
            kwargs={"item_id": self.order_item.id},
        )

        response = self.client.patch(
            url,
            {"is_ready": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PLACED)
        self.assertEqual(response.data["order"]["status"], Order.Status.PLACED)

    @patch("orders.services.transaction.on_commit", side_effect=lambda callback: callback())
    @patch("orders.services.send_store_owner_order_placed_notification.delay")
    def test_create_order_from_cart_notifies_store_owner(
        self,
        send_order_push_notification,
        on_commit,
    ):
        from orders import services

        cart = Cart.objects.create(
            user=self.customer,
            store=self.store,
        )
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            variant=self.variant,
            quantity=1,
        )

        order = services.create_order_from_cart(
            self.customer,
            cart.id,
            None,
            Order.FullfillmentType.SCHEDULED_DELIVERY,
        )

        on_commit.assert_called_once()
        send_order_push_notification.assert_called_once_with(str(order.id))
