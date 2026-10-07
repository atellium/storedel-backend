import math

import pygeohash as pgh
from django.shortcuts import render
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count, Q

from stores.models import SavedStore, Store, StoreSettings
from stores.serializers import (
    MyStoreDetailSerializer,
    NearbyStoreListQuerySerializer,
    NearbyStoreListSerializer,
    SavedStoreSerializer,
    StoreDetailSerializer,
    StoreSettingsUpdateSerializer,
    StoreSettingsSerializer,
    StoreListQuerySerializer,
    StoreListSerializer,
)


GEOHASH_NEARBY_PRECISION = 5
EARTH_RADIUS_KM = 6371.0088


def my_store_order_page(request, store_slug):
    return render(
        request,
        "stores/order_page.html",
        {"store_slug": store_slug},
    )


def _paginated_response(queryset, request, serializer_class, page_size):
    paginator = PageNumberPagination()
    paginator.page_size = page_size
    paginator.page_query_param = "page"
    paginator.page_size_query_param = "page_size"
    page = paginator.paginate_queryset(queryset, request)
    serializer = serializer_class(
        page,
        many=True,
        context={"request": request},
    )
    page_obj = paginator.page
    return Response(
        {
            "count": page_obj.paginator.count,
            "pagination": {
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
            },
            "results": serializer.data,
        }
    )


def _distance_km(lat1, lng1, lat2, lng2):
    lat1 = math.radians(float(lat1))
    lng1 = math.radians(float(lng1))
    lat2 = math.radians(float(lat2))
    lng2 = math.radians(float(lng2))
    lat_delta = lat2 - lat1
    lng_delta = lng2 - lng1
    haversine = (
        math.sin(lat_delta / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(lng_delta / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(haversine))


@api_view(["GET"])
@permission_classes([AllowAny])
def store_list(request):
    query_serializer = StoreListQuerySerializer(data=request.query_params)
    query_serializer.is_valid(raise_exception=True)
    filters = query_serializer.validated_data

    stores = Store.objects.select_related("city", "city__state", "settings")
    stores = stores.filter(is_active=True)
    if filters.get("search"):
        search = filters["search"]
        stores = stores.filter(
            Q(name__icontains=search)
            | Q(address__icontains=search)
            | Q(locality__icontains=search)
            | Q(pincode__icontains=search)
            | Q(phone__icontains=search)
        )
    if filters.get("pincode"):
        stores = stores.filter(pincode=filters["pincode"])
    if filters.get("city"):
        stores = stores.filter(city__slug=filters["city"])
    if filters.get("locality"):
        stores = stores.filter(locality__iexact=filters["locality"])
    if filters.get("geohash"):
        stores = stores.filter(geohash__startswith=filters["geohash"])

    return _paginated_response(
        stores.order_by("name", "id"),
        request,
        StoreListSerializer,
        filters["page_size"],
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def nearby_store_list(request):
    query_serializer = NearbyStoreListQuerySerializer(data=request.query_params)
    query_serializer.is_valid(raise_exception=True)
    filters = query_serializer.validated_data
    lat = filters["lat"]
    lng = filters["lng"]
    geohash = pgh.encode(lat, lng, precision=GEOHASH_NEARBY_PRECISION)

    stores = Store.objects.select_related("city", "city__state", "settings").filter(
        is_active=True,
        latitude__isnull=False,
        longitude__isnull=False,
        geohash__startswith=geohash,
    )
    stores = list(stores)
    for store in stores:
        store.distance_km = round(
            _distance_km(lat, lng, store.latitude, store.longitude),
            3,
        )

    stores.sort(key=lambda store: (store.distance_km, store.name, str(store.id)))

    return _paginated_response(
        stores,
        request,
        NearbyStoreListSerializer,
        filters["page_size"],
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_business_list(request):
    query_serializer = StoreListQuerySerializer(data=request.query_params)
    query_serializer.is_valid(raise_exception=True)
    filters = query_serializer.validated_data

    stores = Store.objects.select_related("city", "city__state", "settings").filter(
        owner=request.user,
    )

    if filters.get("search"):
        search = filters["search"]
        stores = stores.filter(
            Q(name__icontains=search)
            | Q(address__icontains=search)
            | Q(locality__icontains=search)
            | Q(pincode__icontains=search)
            | Q(phone__icontains=search)
        )
    if filters.get("pincode"):
        stores = stores.filter(pincode=filters["pincode"])
    if filters.get("city"):
        stores = stores.filter(city__slug=filters["city"])
    if filters.get("locality"):
        stores = stores.filter(locality__iexact=filters["locality"])
    if filters.get("geohash"):
        stores = stores.filter(geohash__startswith=filters["geohash"])
    if "is_active" in request.query_params:
        stores = stores.filter(is_active=filters["is_active"])

    return _paginated_response(
        stores.order_by("name", "id"),
        request,
        StoreDetailSerializer,
        filters["page_size"],
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_business_detail(request, store_slug):
    store = (
        Store.objects.select_related("city", "city__state", "settings")
        .filter(
            owner=request.user,
            slug=store_slug,
        )
        .annotate(
            total_products=Count("products", distinct=True),
            total_orders=Count("orders", distinct=True),
        )
        .first()
    )
    if store is None:
        raise NotFound("Store not found.")

    return Response(
        {
            "result": MyStoreDetailSerializer(
                store,
                context={"request": request},
            ).data
        }
    )


@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def my_store_settings_update(request, store_slug):
    store = Store.objects.filter(owner=request.user, slug=store_slug).first()
    if store is None:
        raise NotFound("Store not found.")

    store_settings, _ = StoreSettings.objects.get_or_create(
        store=store,
        defaults={
            "is_express_delivery_enabled": False,
            "is_scheduled_delivery_enabled": False,
        },
    )

    if request.method == "GET":
        return Response(
            {
                "result": StoreSettingsSerializer(
                    store_settings,
                    context={"request": request},
                ).data
            }
        )

    serializer = StoreSettingsUpdateSerializer(
        store_settings,
        data=request.data,
        partial=request.method == "PATCH",
        context={"request": request},
    )
    serializer.is_valid(raise_exception=True)
    try:
        store_settings = serializer.save()
    except DjangoValidationError as exc:
        raise ValidationError(exc.message_dict) from exc

    return Response(
        {
            "result": StoreSettingsSerializer(
                store_settings,
                context={"request": request},
            ).data
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def saved_store_list(request):
    query_serializer = StoreListQuerySerializer(data=request.query_params)
    query_serializer.is_valid(raise_exception=True)
    filters = query_serializer.validated_data

    saved_stores = SavedStore.objects.select_related(
        "store",
        "store__city",
        "store__city__state",
        "store__settings",
    ).filter(
        user=request.user,
        store__is_active=True,
    )

    if filters.get("search"):
        search = filters["search"]
        saved_stores = saved_stores.filter(
            Q(store__name__icontains=search)
            | Q(store__address__icontains=search)
            | Q(store__locality__icontains=search)
            | Q(store__pincode__icontains=search)
            | Q(store__phone__icontains=search)
        )
    if filters.get("pincode"):
        saved_stores = saved_stores.filter(store__pincode=filters["pincode"])
    if filters.get("city"):
        saved_stores = saved_stores.filter(store__city__slug=filters["city"])
    if filters.get("locality"):
        saved_stores = saved_stores.filter(store__locality__iexact=filters["locality"])
    if filters.get("geohash"):
        saved_stores = saved_stores.filter(store__geohash__startswith=filters["geohash"])

    return _paginated_response(
        saved_stores.order_by("-created_at", "-id"),
        request,
        SavedStoreSerializer,
        filters["page_size"],
    )


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def saved_store_detail(request, store_slug):
    store = Store.objects.filter(slug=store_slug, is_active=True).first()
    if store is None:
        raise NotFound("Store not found.")

    if request.method == "POST":
        saved_store, created = SavedStore.objects.get_or_create(
            user=request.user,
            store=store,
        )
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(
            {
                "saved": True,
                "result": SavedStoreSerializer(
                    saved_store,
                    context={"request": request},
                ).data,
            },
            status=response_status,
        )

    SavedStore.objects.filter(user=request.user, store=store).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([AllowAny])
def store_settings_detail(request, store_slug):
    store = (
        Store.objects.filter(slug=store_slug, is_active=True)
        .select_related("settings")
        .first()
    )
    if store is None:
        raise NotFound("Store not found.")

    try:
        store_settings = store.settings
    except Store.settings.RelatedObjectDoesNotExist:
        raise NotFound("Store settings not found.")

    return Response(
        {
            "result": StoreSettingsSerializer(
                store_settings,
                context={"request": request},
            ).data
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def store_detail(request, store_slug):
    store = (
        Store.objects.select_related("city", "city__state", "settings")
        .filter(Q(slug=store_slug) | Q(host_name=store_slug), is_active=True)
        .first()
    )
    if store is None:
        raise NotFound("Store not found.")
    return Response(
        {
            "result": StoreDetailSerializer(
                store,
                context={"request": request},
            ).data
        }
    )


