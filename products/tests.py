from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from carts.models import Cart, CartItem
from products.models import Product, ProductCategory, ProductVariant
from stores.models import Store


class ProductCategoryFlatListTests(APITestCase):
    def test_returns_category_slug(self):
        category = ProductCategory.objects.create(
            name="Soft Drink",
            label="Soft Drinks",
            slug="soft-drinks",
            is_active=True,
            is_searchable=True,
        )
        url = reverse("products:product-category-flat-list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["id"], category.pk)
        self.assertEqual(response.data["results"][0]["slug"], category.slug)


class MyStoreProductListTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(phone="+919876543210")
        self.other_user = user_model.objects.create_user(phone="+919876543211")
        self.store = Store.objects.create(
            owner=self.owner,
            name="Owner Store",
            address="Main Road",
            is_active=False,
        )
        self.other_store = Store.objects.create(
            owner=self.other_user,
            name="Other Store",
            address="Other Road",
            is_active=True,
        )
        self.active_product = Product.objects.create(
            store=self.store,
            name="Active Product",
            is_active=True,
        )
        self.inactive_product = Product.objects.create(
            store=self.store,
            name="Inactive Product",
            is_active=False,
        )
        Product.objects.create(
            store=self.other_store,
            name="Other Product",
            is_active=True,
        )

    def test_requires_authentication(self):
        url = reverse(
            "products:my-store-product-list",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.get(url)

        self.assertIn(response.status_code, (401, 403))

    def test_owner_can_list_all_products_for_store(self):
        self.client.force_authenticate(self.owner)
        url = reverse(
            "products:my-store-product-list",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        names = {item["name"] for item in response.data["results"]}
        self.assertEqual(names, {"Active Product", "Inactive Product"})
        self.assertEqual(response.data["store"]["slug"], self.store.slug)

    def test_non_owner_cannot_list_store_products(self):
        self.client.force_authenticate(self.other_user)
        url = reverse(
            "products:my-store-product-list",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_public_store_product_list_still_returns_active_products_only(self):
        url = reverse(
            "products:store-product-list",
            kwargs={"store_slug": self.store.slug},
        )
        self.store.is_active = True
        self.store.save(update_fields=["is_active"])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        names = {item["name"] for item in response.data["results"]}
        self.assertEqual(names, {"Active Product"})

    def test_public_store_product_list_can_filter_custom_quantity_products(self):
        self.active_product.allow_custom_quantity = True
        self.active_product.measurement_type = Product.MeasurementType.WEIGHT
        self.active_product.base_quantity = 1000
        self.active_product.base_price = 50
        self.active_product.minimum_quantity = 100
        self.active_product.quantity_step = 50
        self.active_product.save()
        Product.objects.create(
            store=self.store,
            name="Fixed Product",
            is_active=True,
        )
        self.store.is_active = True
        self.store.save(update_fields=["is_active"])
        url = reverse(
            "products:store-product-list",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.get(url, {"is_custom_quantity": "true"})

        self.assertEqual(response.status_code, 200)
        names = {item["name"] for item in response.data["results"]}
        self.assertEqual(names, {"Active Product"})

    def test_owner_store_product_list_can_filter_non_custom_quantity_products(self):
        self.active_product.allow_custom_quantity = True
        self.active_product.measurement_type = Product.MeasurementType.WEIGHT
        self.active_product.base_quantity = 1000
        self.active_product.base_price = 50
        self.active_product.minimum_quantity = 100
        self.active_product.quantity_step = 50
        self.active_product.save()
        self.client.force_authenticate(self.owner)
        url = reverse(
            "products:my-store-product-list",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.get(url, {"is_custom_quantity": "false"})

        self.assertEqual(response.status_code, 200)
        names = {item["name"] for item in response.data["results"]}
        self.assertEqual(names, {"Inactive Product"})

    def test_public_store_product_list_includes_category_with_child_related(self):
        parent = ProductCategory.objects.create(
            name="Beverage",
            label="Beverages",
            slug="beverages",
            sort_order=1,
        )
        child = ProductCategory.objects.create(
            parent=parent,
            name="Tea",
            label="Tea",
            slug="tea",
            sort_order=1,
        )
        ProductCategory.objects.create(
            parent=parent,
            name="Coffee",
            label="Coffee",
            slug="coffee",
            sort_order=2,
        )
        self.active_product.categories.add(parent)
        self.store.is_active = True
        self.store.save(update_fields=["is_active"])
        url = reverse(
            "products:store-product-list",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.get(url, {"category": parent.slug})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["category"]["slug"], parent.slug)
        self.assertEqual(
            [item["slug"] for item in response.data["category"]["related"]],
            [child.slug, "coffee"],
        )

    def test_public_product_detail_by_slug_returns_active_product(self):
        self.store.is_active = True
        self.store.save(update_fields=["is_active"])
        variant = ProductVariant.objects.create(
            product=self.active_product,
            value=None,
            unit=ProductVariant.Unit.PACK,
            pack_count=1,
            price=50,
            is_active=True,
        )
        inactive_variant = ProductVariant.objects.create(
            product=self.active_product,
            value=None,
            unit=ProductVariant.Unit.BOX,
            pack_count=1,
            price=60,
            is_active=False,
        )
        url = reverse(
            "products:product-detail-by-slug",
            kwargs={
                "product_slug": self.active_product.slug,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["product"]["id"], str(self.active_product.pk))
        self.assertEqual(response.data["product"]["slug"], self.active_product.slug)
        self.assertEqual(
            response.data["product"]["store"],
            {
                "id": str(self.store.id),
                "name": self.store.name,
                "slug": self.store.slug,
            },
        )
        self.assertEqual(
            [item["id"] for item in response.data["product"]["variants"]],
            [str(variant.pk)],
        )
        self.assertEqual(response.data["product"]["variants"][0]["cart_count"], 0)
        self.assertNotIn(
            str(inactive_variant.pk),
            [item["id"] for item in response.data["product"]["variants"]],
        )

    def test_public_product_detail_variant_includes_active_cart_count(self):
        self.store.is_active = True
        self.store.save(update_fields=["is_active"])
        variant = ProductVariant.objects.create(
            product=self.active_product,
            value=None,
            unit=ProductVariant.Unit.PACK,
            pack_count=1,
            price=50,
            is_active=True,
        )
        cart = Cart.objects.create(user=self.owner, store=self.store)
        CartItem.objects.create(
            cart=cart,
            product=self.active_product,
            variant=variant,
            quantity=3,
        )
        self.client.force_authenticate(self.owner)
        url = reverse(
            "products:product-detail-by-slug",
            kwargs={
                "product_slug": self.active_product.slug,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["product"]["variants"][0]["cart_count"], 3)

    def test_public_product_detail_by_slug_hides_inactive_product(self):
        self.store.is_active = True
        self.store.save(update_fields=["is_active"])
        url = reverse(
            "products:product-detail-by-slug",
            kwargs={
                "product_slug": self.inactive_product.slug,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_public_store_product_list_child_category_related_uses_parent_children(self):
        parent = ProductCategory.objects.create(
            name="Beverage",
            label="Beverages",
            slug="beverages",
        )
        tea = ProductCategory.objects.create(
            parent=parent,
            name="Tea",
            label="Tea",
            slug="tea",
            sort_order=1,
        )
        coffee = ProductCategory.objects.create(
            parent=parent,
            name="Coffee",
            label="Coffee",
            slug="coffee",
            sort_order=2,
        )
        self.active_product.categories.add(tea)
        self.store.is_active = True
        self.store.save(update_fields=["is_active"])
        url = reverse(
            "products:store-product-list",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.get(url, {"category": tea.slug})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["category"]["slug"], tea.slug)
        self.assertEqual(
            [item["slug"] for item in response.data["category"]["related"]],
            [tea.slug, coffee.slug],
        )

    def test_owner_can_create_product_for_store(self):
        self.client.force_authenticate(self.owner)
        url = reverse(
            "products:my-store-product-list",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.post(url, {"name": "New Product"}, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["product"]["name"], "New Product")
        self.assertTrue(
            Product.objects.filter(
                store=self.store,
                name="New Product",
            ).exists()
        )

    def test_custom_quantity_product_gets_default_variant(self):
        self.client.force_authenticate(self.owner)
        url = reverse(
            "products:my-store-product-list",
            kwargs={"store_slug": self.store.slug},
        )

        response = self.client.post(
            url,
            {
                "name": "Loose Sugar",
                "measurement_type": Product.MeasurementType.WEIGHT,
                "allow_custom_quantity": True,
                "base_quantity": 1000,
                "base_price": 55,
                "minimum_quantity": 100,
                "quantity_step": 50,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        variants = response.data["product"]["variants"]
        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0]["value"], 1000)
        self.assertEqual(variants[0]["unit"], ProductVariant.Unit.GRAM)
        self.assertEqual(variants[0]["price"], 55)
        self.assertTrue(variants[0]["is_default"])

        product = Product.objects.get(pk=response.data["product"]["id"])
        variant = product.variants.get()
        self.assertEqual(variant.value, 1000)
        self.assertEqual(variant.price, 55)
        self.assertTrue(variant.is_default)

    def test_owner_can_view_product_for_store(self):
        self.client.force_authenticate(self.owner)
        url = reverse(
            "products:my-store-product-detail",
            kwargs={
                "store_slug": self.store.slug,
                "product_id": self.inactive_product.pk,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["product"]["name"], "Inactive Product")

    def test_owner_can_update_product_for_store(self):
        self.client.force_authenticate(self.owner)
        url = reverse(
            "products:my-store-product-detail",
            kwargs={
                "store_slug": self.store.slug,
                "product_id": self.active_product.pk,
            },
        )

        response = self.client.patch(
            url,
            {"name": "Updated Product", "is_active": False},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.active_product.refresh_from_db()
        self.assertEqual(self.active_product.name, "Updated Product")
        self.assertFalse(self.active_product.is_active)

    def test_owner_can_delete_product_for_store(self):
        self.client.force_authenticate(self.owner)
        product_id = self.active_product.pk
        url = reverse(
            "products:my-store-product-detail",
            kwargs={
                "store_slug": self.store.slug,
                "product_id": product_id,
            },
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Product.objects.filter(pk=product_id).exists())

    def test_owner_cannot_manage_product_through_wrong_store(self):
        self.client.force_authenticate(self.owner)
        url = reverse(
            "products:my-store-product-detail",
            kwargs={
                "store_slug": self.other_store.slug,
                "product_id": self.active_product.pk,
            },
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_owner_can_bulk_create_product_variants(self):
        self.client.force_authenticate(self.owner)
        url = reverse(
            "products:my-store-product-variant-list",
            kwargs={
                "store_slug": self.store.slug,
                "product_id": self.active_product.pk,
            },
        )

        response = self.client.post(
            url,
            {
                "variants": [
                    {
                        "value": None,
                        "unit": ProductVariant.Unit.PACK,
                        "pack_count": 1,
                        "price": 50,
                        "mrp": 60,
                        "cost_price": 40,
                        "is_default": True,
                        "is_active": True,
                        "sort_order": 0,
                    },
                    {
                        "value": None,
                        "unit": ProductVariant.Unit.BOX,
                        "pack_count": 1,
                        "price": 450,
                        "mrp": 500,
                        "cost_price": 380,
                        "is_active": True,
                        "sort_order": 1,
                    },
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(
            ProductVariant.objects.filter(product=self.active_product).count(),
            2,
        )
        self.assertIn("cost_price", response.data["results"][0])

    def test_owner_can_bulk_update_and_create_product_variants(self):
        existing_variant = ProductVariant.objects.create(
            product=self.active_product,
            value=None,
            unit=ProductVariant.Unit.PACK,
            pack_count=1,
            price=50,
            mrp=60,
            cost_price=40,
            is_default=True,
        )
        self.client.force_authenticate(self.owner)
        url = reverse(
            "products:my-store-product-variant-list",
            kwargs={
                "store_slug": self.store.slug,
                "product_id": self.active_product.pk,
            },
        )

        response = self.client.patch(
            url,
            [
                {
                    "id": str(existing_variant.pk),
                    "price": 55,
                    "cost_price": 42,
                },
                {
                    "value": None,
                    "unit": ProductVariant.Unit.BOX,
                    "pack_count": 1,
                    "price": 450,
                    "is_active": True,
                },
            ],
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        existing_variant.refresh_from_db()
        self.assertEqual(existing_variant.price, 55)
        self.assertEqual(existing_variant.cost_price, 42)
        self.assertEqual(
            ProductVariant.objects.filter(product=self.active_product).count(),
            2,
        )

    def test_owner_can_delete_product_variant(self):
        variant = ProductVariant.objects.create(
            product=self.active_product,
            value=None,
            unit=ProductVariant.Unit.PACK,
            pack_count=1,
            price=50,
        )
        self.client.force_authenticate(self.owner)
        url = reverse(
            "products:my-store-product-variant-detail",
            kwargs={
                "store_slug": self.store.slug,
                "product_id": self.active_product.pk,
                "variant_id": variant.pk,
            },
        )

        response = self.client.delete(url)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(ProductVariant.objects.filter(pk=variant.pk).exists())

    def test_non_owner_cannot_bulk_create_product_variants(self):
        self.client.force_authenticate(self.other_user)
        url = reverse(
            "products:my-store-product-variant-list",
            kwargs={
                "store_slug": self.store.slug,
                "product_id": self.active_product.pk,
            },
        )

        response = self.client.post(
            url,
            [
                {
                    "value": None,
                    "unit": ProductVariant.Unit.PACK,
                    "pack_count": 1,
                    "price": 50,
                }
            ],
            format="json",
        )

        self.assertEqual(response.status_code, 404)
