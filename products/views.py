from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.exceptions import NotAuthenticated, NotFound
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from products import services
from products.serializers import (
    ProductListSerializer,
    ProductCategoryFlatSerializer,
    ProductCategoryImportSerializer,
    ProductCategoryListQuerySerializer,
    ProductCategorySerializer,
    OwnerProductVariantSerializer,
    ProductVariantWriteSerializer,
    ProductWriteSerializer,
    StoreProductListQuerySerializer,
)
from stores.models import Store


def _get_product_response(product, request, status=None):
    product = services.get_product_for_response(product)
    return Response(
        {
            "product": ProductListSerializer(
                product,
                context={"request": request},
            ).data
        },
        status=status,
    )


def _get_variant_items(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "variants" in data:
        return data["variants"]
    return [data]


def _get_category_response_data(filters, request):
    if not filters.get("category"):
        return None

    category, related = services.get_category_with_related(filters["category"])
    context = {"request": request}
    category_data = ProductCategorySerializer(category, context=context).data
    category_data["related"] = ProductCategoryFlatSerializer(
        related,
        many=True,
        context=context,
    ).data
    return category_data


def _remove_absent_boolean_filters(filters, query_params):
    for field in ("is_custom_quantity", "is_featured"):
        if field not in query_params:
            filters.pop(field, None)


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def store_product_list(request, store_slug):
    if request.method == "POST":
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated("Authentication credentials were not provided.")

        serializer = ProductWriteSerializer(
            data=request.data,
            context={"is_create": True},
        )
        serializer.is_valid(raise_exception=True)
        product = services.create_product(
            request.user,
            store_slug,
            serializer.validated_data,
        )
        return _get_product_response(product, request, status=201)

    query_serializer = StoreProductListQuerySerializer(data=request.query_params)
    query_serializer.is_valid(raise_exception=True)
    filters = query_serializer.validated_data
    _remove_absent_boolean_filters(filters, request.query_params)

    store = Store.objects.filter(slug=store_slug, is_active=True).first()
    if store is None:
        raise NotFound("Store not found.")

    products = services.list_store_products(store, filters)
    page, _, pagination = services.paginate_queryset(
        products,
        request,
        filters["page_size"],
    )
    serializer = ProductListSerializer(page, many=True, context={"request": request})
    response_data = {
        "store": {
            "id": store.pk,
            "name": store.name,
            "slug": store.slug,
        },
        "pagination": pagination,
    }
    category_data = _get_category_response_data(filters, request)
    if category_data is not None:
        response_data["category"] = category_data
    response_data["results"] = serializer.data

    return Response(response_data)


@api_view(["GET"])
@permission_classes([AllowAny])
def product_detail_by_slug(request, product_slug):
    product = services.get_public_product_by_slug(product_slug)
    return Response(
        {
            "product": ProductListSerializer(
                product,
                context={"request": request},
            ).data
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def my_store_product_list(request, store_slug):
    if request.method == "POST":
        serializer = ProductWriteSerializer(
            data=request.data,
            context={"is_create": True},
        )
        serializer.is_valid(raise_exception=True)
        product = services.create_store_product(
            request.user,
            store_slug,
            serializer.validated_data,
        )
        return _get_product_response(product, request, status=201)

    query_serializer = StoreProductListQuerySerializer(data=request.query_params)
    query_serializer.is_valid(raise_exception=True)
    filters = query_serializer.validated_data
    _remove_absent_boolean_filters(filters, request.query_params)

    store = services.get_user_store(request.user, store_slug)
    products = services.list_store_products(store, filters, active_only=False)
    page, _, pagination = services.paginate_queryset(
        products,
        request,
        filters["page_size"],
    )
    serializer = ProductListSerializer(page, many=True, context={"request": request})
    return Response(
        {
            "store": {
                "id": store.pk,
                "name": store.name,
                "slug": store.slug,
            },
            "pagination": pagination,
            "results": serializer.data,
        }
    )


@api_view(["GET", "PATCH", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def my_store_product_detail(request, store_slug, product_id):
    if request.method == "GET":
        product = services.get_user_store_product(
            request.user,
            store_slug,
            product_id,
        )
        return _get_product_response(product, request)

    if request.method == "DELETE":
        services.delete_store_product(
            request.user,
            store_slug,
            product_id,
        )
        return Response(status=204)

    serializer = ProductWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    product = services.update_store_product(
        request.user,
        store_slug,
        product_id,
        serializer.validated_data,
    )
    return _get_product_response(product, request)


@api_view(["GET", "POST", "PATCH"])
@permission_classes([IsAuthenticated])
def my_store_product_variant_list(request, store_slug, product_id):
    if request.method == "GET":
        variants = services.list_store_product_variants(
            request.user,
            store_slug,
            product_id,
        )
        serializer = OwnerProductVariantSerializer(variants, many=True)
        return Response({"results": serializer.data})

    items = _get_variant_items(request.data)
    serializer = ProductVariantWriteSerializer(data=items, many=True)
    serializer.is_valid(raise_exception=True)

    variants = services.bulk_upsert_store_product_variants(
        request.user,
        store_slug,
        product_id,
        serializer.validated_data,
    )
    response_serializer = OwnerProductVariantSerializer(variants, many=True)
    return Response(
        {"results": response_serializer.data},
        status=201 if request.method == "POST" else 200,
    )


@api_view(["GET", "PATCH", "PUT", "DELETE"])
@permission_classes([IsAuthenticated])
def my_store_product_variant_detail(request, store_slug, product_id, variant_id):
    if request.method == "GET":
        variant = services.get_store_product_variant(
            request.user,
            store_slug,
            product_id,
            variant_id,
        )
        return Response({"variant": OwnerProductVariantSerializer(variant).data})

    if request.method == "DELETE":
        services.delete_store_product_variant(
            request.user,
            store_slug,
            product_id,
            variant_id,
        )
        return Response(status=204)

    serializer = ProductVariantWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    variant = services.update_store_product_variant(
        request.user,
        store_slug,
        product_id,
        variant_id,
        serializer.validated_data,
    )
    return Response({"variant": OwnerProductVariantSerializer(variant).data})


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def product_detail(request, product_id):
    serializer = ProductWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    product = services.update_product(
        request.user,
        product_id,
        serializer.validated_data,
    )
    return _get_product_response(product, request)


@api_view(["GET"])
@permission_classes([AllowAny])
def product_category_flat_list(request):
    categories = services.list_flat_product_categories()
    serializer = ProductCategoryFlatSerializer(categories, many=True)
    return Response({"results": serializer.data})


@api_view(["GET"])
@permission_classes([AllowAny])
def product_category_list(request):
    query_serializer = ProductCategoryListQuerySerializer(data=request.query_params)
    query_serializer.is_valid(raise_exception=True)
    filters = query_serializer.validated_data

    categories = services.list_product_categories(filters, request.query_params)
    page, count, pagination = services.paginate_queryset(
        categories,
        request,
        filters["page_size"],
    )
    serializer = ProductCategorySerializer(
        page,
        many=True,
        context={"request": request},
    )
    return Response(
        {
            "count": count,
            "pagination": pagination,
            "results": serializer.data,
        }
    )


@api_view(["POST"])
@permission_classes([IsAdminUser])
@parser_classes([MultiPartParser, FormParser])
def import_product_categories(request):
    serializer = ProductCategoryImportSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    parent = serializer.validated_data.get("parent_id")
    categories = serializer.validated_data["file"].categories

    created_categories = services.import_product_categories(parent, categories)

    return Response(
        {
            "message": "Product categories imported successfully.",
            "created_count": len(created_categories),
            "results": ProductCategorySerializer(created_categories, many=True).data,
        },
        status=201,
    )
