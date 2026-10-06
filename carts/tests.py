from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from products.models import Product, ProductVariant
from stores.models import Store
from uploads.models import Upload


class CartResponseTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(phone="+919876543210")
        self.store = Store.objects.create(
            owner=self.user,
            name="Cart Store",
            address="Main Road",
            is_active=True,
        )
        self.product = Product.objects.create(
            store=self.store,
            name="Tea Pack",
            is_active=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            value=None,
            unit=ProductVariant.Unit.PACK,
            pack_count=1,
            price=120,
            is_active=True,
        )
        self.upload = Upload.objects.create(
            object_key="uploads/products/tea.webp",
            mime_type="image/webp",
            title="Tea",
            status=Upload.Status.READY,
            uploaded_by=self.user,
        )
        self.product.uploads.add(self.upload)

    def test_cart_item_includes_product_image_url(self):
        self.client.force_authenticate(self.user)
        url = reverse(
            "carts:cart-item-add",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.post(
            url,
            {
                "product_id": str(self.product.pk),
                "variant_id": str(self.variant.pk),
                "quantity": 1,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        item = response.data["cart"]["items"][0]
        self.assertIn("product_image_url", item)
        self.assertTrue(item["product_image_url"].endswith("/uploads/products/tea.webp"))

    def test_custom_quantity_variant_updates_existing_custom_item(self):
        custom_product = Product.objects.create(
            store=self.store,
            name="Loose Sugar",
            measurement_type=Product.MeasurementType.WEIGHT,
            allow_custom_quantity=True,
            base_quantity=1000,
            base_price=60,
            minimum_quantity=50,
            quantity_step=50,
            is_active=True,
        )
        variant = ProductVariant.objects.create(
            product=custom_product,
            value=500,
            unit=ProductVariant.Unit.GRAM,
            pack_count=1,
            price=30,
            is_active=True,
        )
        self.client.force_authenticate(self.user)
        url = reverse(
            "carts:cart-item-add",
            kwargs={"store_slug": self.store.slug},
        )

        first_response = self.client.post(
            url,
            {
                "product_id": str(custom_product.pk),
                "custom_value": 250,
                "quantity": 1,
            },
            format="json",
        )
        second_response = self.client.post(
            url,
            {
                "product_id": str(custom_product.pk),
                "variant_id": str(variant.pk),
                "quantity": 1,
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 201)
        items = second_response.data["cart"]["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["custom_value"], 500)
        self.assertEqual(items[0]["variant_id"], None)
        self.assertEqual(items[0]["quantity"], 2)
