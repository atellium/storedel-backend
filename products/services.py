from django.db import transaction
from django.db.models import Prefetch, Q
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination

from products.models import Product, ProductCategory, ProductVariant
from stores.models import Store
from uploads.models import Upload


CATEGORY_FIELDS = {
    "name",
    "label",
    "display_name",
    "slug",
    "aliases",
    "sort_order",
    "is_active",
    "is_featured",
    "is_searchable",
}


def list_flat_product_categories():
    return ProductCategory.objects.filter(
        is_active=True,
        is_searchable=True,
    ).order_by("sort_order", "name", "id")


def list_store_products(store, filters, active_only=True):
    product_filters = {"store": store}
    variant_filters = {}
    if active_only:
        product_filters["is_active"] = True
        variant_filters["is_active"] = True

    products = (
        Product.objects.filter(**product_filters)
        .prefetch_related(
            Prefetch(
                "categories",
                queryset=ProductCategory.objects.filter(is_active=True).order_by(
                    "sort_order",
                    "name",
                    "id",
                ),
            ),
            Prefetch(
                "variants",
                queryset=ProductVariant.objects.filter(**variant_filters).order_by(
                    "sort_order",
                    "value",
                    "pack_count",
                ),
            ),
            Prefetch(
                "uploads",
                queryset=Upload.objects.filter(status=Upload.Status.READY).order_by(
                    "-created_at",
                    "id",
                ),
            ),
        )
    )

    if filters.get("category"):
        category_ids = get_category_with_descendant_ids(filters["category"])
        products = products.filter(
            categories__id__in=category_ids,
        )

    if "is_custom_quantity" in filters:
        products = products.filter(
            allow_custom_quantity=filters["is_custom_quantity"],
        )

    if filters.get("search"):
        search = filters["search"]
        products = products.filter(
            Q(name__icontains=search)
            | Q(short_description__icontains=search)
            | Q(brand__icontains=search)
            | Q(slug__icontains=search)
            | Q(public_id__icontains=search)
        )

    return products.distinct().order_by("sort_order", "-created_at", "id")


def get_category_with_descendant_ids(category_slug):
    category = ProductCategory.objects.filter(
        slug=category_slug,
        is_active=True,
    ).first()
    if category is None:
        raise NotFound("Category not found.")

    category_ids = [category.id]
    parent_ids = [category.id]

    while parent_ids:
        child_ids = list(
            ProductCategory.objects.filter(
                parent_id__in=parent_ids,
                is_active=True,
            ).values_list("id", flat=True)
        )
        category_ids.extend(child_ids)
        parent_ids = child_ids

    return category_ids


def get_category_with_related(category_slug):
    category = (
        ProductCategory.objects.select_related("parent")
        .filter(slug=category_slug, is_active=True)
        .first()
    )
    if category is None:
        raise NotFound("Category not found.")

    children = ProductCategory.objects.filter(
        parent=category,
        is_active=True,
    ).order_by("sort_order", "name", "id")
    if children.exists():
        return category, children

    if category.parent_id:
        siblings = ProductCategory.objects.filter(
            parent=category.parent,
            is_active=True,
        ).order_by("sort_order", "name", "id")
        return category, siblings

    return category, ProductCategory.objects.none()


def get_user_store(user, store_slug):
    store = Store.objects.filter(owner=user, slug=store_slug).first()
    if store is None:
        raise NotFound("Store not found.")

    return store


def get_store_for_product_write(user, store_slug):
    store = Store.objects.filter(slug=store_slug).first()
    if store is None:
        raise NotFound("Store not found.")

    if not user.is_staff and store.owner_id != user.pk:
        raise PermissionDenied("You do not have permission to manage this store.")

    return store


def get_user_product_for_update(user, product_id):
    product = (
        Product.objects.select_related("store")
        .prefetch_related("categories", "uploads", "variants")
        .filter(pk=product_id)
        .first()
    )
    if product is None:
        raise NotFound("Product not found.")

    if not user.is_staff and product.store.owner_id != user.pk:
        raise PermissionDenied("You do not have permission to manage this product.")

    return product


def get_user_store_product(user, store_slug, product_id):
    product = (
        Product.objects.select_related("store")
        .prefetch_related("categories", "uploads", "variants")
        .filter(
            pk=product_id,
            store__slug=store_slug,
            store__owner=user,
        )
        .first()
    )
    if product is None:
        raise NotFound("Product not found.")

    return product


def get_public_product_by_slug(product_slug):
    product = (
        Product.objects.select_related("store")
        .prefetch_related(
            Prefetch(
                "categories",
                queryset=ProductCategory.objects.filter(is_active=True).order_by(
                    "sort_order",
                    "name",
                    "id",
                ),
            ),
            Prefetch(
                "variants",
                queryset=ProductVariant.objects.filter(is_active=True).order_by(
                    "sort_order",
                    "value",
                    "pack_count",
                ),
            ),
            Prefetch(
                "uploads",
                queryset=Upload.objects.filter(status=Upload.Status.READY).order_by(
                    "-created_at",
                    "id",
                ),
            ),
        )
        .filter(
            slug=product_slug,
            is_active=True,
            store__is_active=True,
        )
        .first()
    )
    if product is None:
        raise NotFound("Product not found.")

    return product


def get_product_for_response(product):
    return (
        Product.objects.select_related("store")
        .prefetch_related(
            "categories",
            "uploads",
            "variants",
        )
        .get(pk=product.pk)
    )


def create_product(user, store_slug, data):
    store = get_store_for_product_write(user, store_slug)
    category_ids = data.pop("category_ids", [])
    upload_ids = data.pop("upload_ids", [])

    with transaction.atomic():
        product = Product(store=store, **data)
        save_product(product)
        set_product_relations(product, category_ids, upload_ids, user)

    return product


def create_store_product(user, store_slug, data):
    store = get_user_store(user, store_slug)
    category_ids = data.pop("category_ids", [])
    upload_ids = data.pop("upload_ids", [])

    with transaction.atomic():
        product = Product(store=store, **data)
        save_product(product)
        set_product_relations(product, category_ids, upload_ids, user)

    return product


def update_product(user, product_id, data):
    product = get_user_product_for_update(user, product_id)
    category_ids = data.pop("category_ids", None)
    upload_ids = data.pop("upload_ids", None)

    for field, value in data.items():
        setattr(product, field, value)

    save_product(product)
    set_product_relations(product, category_ids, upload_ids, user)
    return product


def update_store_product(user, store_slug, product_id, data):
    product = get_user_store_product(user, store_slug, product_id)
    category_ids = data.pop("category_ids", None)
    upload_ids = data.pop("upload_ids", None)

    for field, value in data.items():
        setattr(product, field, value)

    save_product(product)
    set_product_relations(product, category_ids, upload_ids, user)
    return product


def delete_store_product(user, store_slug, product_id):
    product = get_user_store_product(user, store_slug, product_id)
    product.delete()


def list_store_product_variants(user, store_slug, product_id):
    product = get_user_store_product(user, store_slug, product_id)
    return product.variants.order_by("sort_order", "value", "unit", "pack_count")


def get_store_product_variant(user, store_slug, product_id, variant_id):
    product = get_user_store_product(user, store_slug, product_id)
    variant = product.variants.filter(pk=variant_id).first()
    if variant is None:
        raise NotFound("Product variant not found.")

    return variant


def create_store_product_variant(user, store_slug, product_id, data):
    product = get_user_store_product(user, store_slug, product_id)
    variant = ProductVariant(product=product, **data)
    save_product_variant(variant)
    return variant


def update_store_product_variant(user, store_slug, product_id, variant_id, data):
    variant = get_store_product_variant(user, store_slug, product_id, variant_id)
    for field, value in data.items():
        setattr(variant, field, value)

    save_product_variant(variant)
    return variant


def delete_store_product_variant(user, store_slug, product_id, variant_id):
    variant = get_store_product_variant(user, store_slug, product_id, variant_id)
    variant.delete()


def bulk_upsert_store_product_variants(user, store_slug, product_id, items):
    product = get_user_store_product(user, store_slug, product_id)
    variants = []

    with transaction.atomic():
        for data in items:
            data = data.copy()
            variant_id = data.pop("id", None)

            if variant_id:
                variant = product.variants.filter(pk=variant_id).first()
                if variant is None:
                    raise NotFound("Product variant not found.")
                for field, value in data.items():
                    setattr(variant, field, value)
            else:
                variant = ProductVariant(product=product, **data)

            save_product_variant(variant)
            variants.append(variant)

    return ProductVariant.objects.filter(
        pk__in=[variant.pk for variant in variants],
    ).order_by("sort_order", "value", "unit", "pack_count")


def set_product_relations(product, category_ids, upload_ids, user):
    if category_ids is not None:
        product.categories.set(get_categories(category_ids))

    if upload_ids is not None:
        product.uploads.set(get_uploads(upload_ids, user))


def get_categories(category_ids):
    categories = list(ProductCategory.objects.filter(id__in=category_ids))
    found_ids = {category.id for category in categories}
    missing_ids = set(category_ids) - found_ids
    if missing_ids:
        raise ValidationError(
            {
                "category_ids": (
                    "Categories not found: "
                    + ", ".join(str(category_id) for category_id in sorted(missing_ids))
                )
            }
        )
    return categories


def get_uploads(upload_ids, user):
    uploads = Upload.objects.filter(
        id__in=upload_ids,
        status=Upload.Status.READY,
    )

    if not user.is_staff:
        uploads = uploads.filter(uploaded_by=user)

    uploads = list(uploads)
    found_ids = {upload.id for upload in uploads}
    missing_ids = set(upload_ids) - found_ids
    if missing_ids:
        raise ValidationError(
            {
                "upload_ids": (
                    "Ready uploads not found: "
                    + ", ".join(str(upload_id) for upload_id in sorted(missing_ids))
                )
            }
        )
    return uploads


def save_product(product):
    try:
        exclude = ["slug"] if not product.slug else None
        product.full_clean(exclude=exclude)
        product.save()
    except DjangoValidationError as exc:
        raise ValidationError(exc.message_dict) from exc
    return product


def save_product_variant(variant):
    with transaction.atomic():
        try:
            if variant.is_default:
                ProductVariant.objects.filter(
                    product=variant.product,
                    is_default=True,
                ).exclude(pk=variant.pk).update(is_default=False)
            variant.full_clean()
            variant.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict) from exc
    return variant


def list_product_categories(filters, query_params):
    categories = ProductCategory.objects.select_related("parent")

    if filters.get("search"):
        search = filters["search"]
        categories = categories.filter(
            Q(name__icontains=search)
            | Q(label__icontains=search)
            | Q(display_name__icontains=search)
            | Q(slug__icontains=search)
            | Q(aliases__icontains=search)
        )
    if "parent_slug" in query_params:
        categories = categories.filter(parent__slug=filters["parent_slug"])
    if query_params.get("root_only") and filters["root_only"]:
        categories = categories.filter(parent__isnull=True)
    if "is_active" in query_params:
        categories = categories.filter(is_active=filters["is_active"])
    if "is_featured" in query_params:
        categories = categories.filter(is_featured=filters["is_featured"])
    if "is_searchable" in query_params:
        categories = categories.filter(is_searchable=filters["is_searchable"])

    return categories.order_by(filters["ordering"], "id")


def paginate_queryset(queryset, request, page_size):
    paginator = PageNumberPagination()
    paginator.page_size = page_size
    paginator.page_query_param = "page"
    paginator.page_size_query_param = "page_size"
    page = paginator.paginate_queryset(queryset, request)
    page_obj = paginator.page
    pagination = {
        "page": page_obj.number,
        "page_size": paginator.get_page_size(request),
        "total_items": page_obj.paginator.count,
        "total_pages": page_obj.paginator.num_pages,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
        "next_page": (
            page_obj.next_page_number()
            if page_obj.has_next()
            else None
        ),
        "previous_page": (
            page_obj.previous_page_number()
            if page_obj.has_previous()
            else None
        ),
    }
    return page, page_obj.paginator.count, pagination


def create_product_categories(items, parent):
    created = []
    for index, item in enumerate(items, start=1):
        data = {field: item[field] for field in CATEGORY_FIELDS if field in item}
        if not data.get("name"):
            raise ValidationError({"file": f"Category at index {index} needs name."})
        if not data.get("label"):
            raise ValidationError({"file": f"Category at index {index} needs label."})

        category = ProductCategory.objects.create(parent=parent, **data)
        created.append(category)

    return created


def import_product_categories(parent, categories):
    with transaction.atomic():
        return create_product_categories(categories, parent)
