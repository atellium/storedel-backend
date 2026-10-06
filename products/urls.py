from django.urls import path

from products import views


app_name = "products"

urlpatterns = [
    path(
        "stores/my/<slug:store_slug>/products/",
        views.my_store_product_list,
        name="my-store-product-list",
    ),
    path(
        "stores/my/<slug:store_slug>/products/<uuid:product_id>/",
        views.my_store_product_detail,
        name="my-store-product-detail",
    ),
    path(
        "stores/my/<slug:store_slug>/products/<uuid:product_id>/variants/",
        views.my_store_product_variant_list,
        name="my-store-product-variant-list",
    ),
    path(
        "stores/my/<slug:store_slug>/products/<uuid:product_id>/variants/<uuid:variant_id>/",
        views.my_store_product_variant_detail,
        name="my-store-product-variant-detail",
    ),
    path(
        "stores/<slug:store_slug>/products/",
        views.store_product_list,
        name="store-product-list",
    ),
    path(
        "product/<slug:product_slug>/",
        views.product_detail_by_slug,
        name="product-detail-by-slug",
    ),
    path(
        "products/<uuid:product_id>/",
        views.product_detail,
        name="product-detail",
    ),
    path(
        "product-categories/flat/",
        views.product_category_flat_list,
        name="product-category-flat-list",
    ),
    path(
        "product-categories/",
        views.product_category_list,
        name="product-category-list",
    ),
    path(
        "product-categories/import/",
        views.import_product_categories,
        name="product-category-import",
    ),
]
