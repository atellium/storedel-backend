from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from locations.models import Address
from locations.serializers import (
    AddressSerializer,
    CityListQuerySerializer,
    CitySerializer,
)
from locations.services import list_cities


@api_view(["GET"])
@permission_classes([AllowAny])
def city_list(request):
    query_serializer = CityListQuerySerializer(data=request.query_params)
    query_serializer.is_valid(raise_exception=True)
    filters = query_serializer.validated_data

    cities = list_cities(
        search=filters.get("search"),
        pincode_prefix=filters.get("pincode_prefix"),
    )
    return Response(CitySerializer(cities, many=True).data)


def _user_address_queryset(user):
    return Address.objects.select_related("city", "city__state").filter(user=user)


def _get_user_address(user, address_id):
    address = _user_address_queryset(user).filter(id=address_id).first()
    if address is None:
        raise NotFound("Address not found.")
    return address


def _save_address(serializer, user):
    with transaction.atomic():
        will_be_default = serializer.validated_data.get(
            "is_default",
            serializer.instance.is_default if serializer.instance else False,
        )
        if will_be_default:
            existing_default_addresses = Address.objects.filter(
                user=user,
                is_default=True,
            )
            if serializer.instance is not None:
                existing_default_addresses = existing_default_addresses.exclude(
                    id=serializer.instance.id,
                )
            existing_default_addresses.update(is_default=False)

        save_kwargs = {}
        if serializer.instance is None:
            save_kwargs["user"] = user
        address = serializer.save(**save_kwargs)
    return address


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def user_address_list(request):
    if request.method == "GET":
        addresses = _user_address_queryset(request.user)
        return Response({"results": AddressSerializer(addresses, many=True).data})

    serializer = AddressSerializer(data=request.data, context={"user": request.user})
    serializer.is_valid(raise_exception=True)
    address = _save_address(serializer, request.user)
    return Response({"result": AddressSerializer(address).data}, status=201)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def user_address_detail(request, address_id):
    address = _get_user_address(request.user, address_id)

    if request.method == "GET":
        return Response({"result": AddressSerializer(address).data})

    if request.method == "DELETE":
        address.delete()
        return Response(status=204)

    serializer = AddressSerializer(
        address,
        data=request.data,
        partial=request.method == "PATCH",
        context={"user": request.user},
    )
    serializer.is_valid(raise_exception=True)
    address = _save_address(serializer, request.user)
    return Response({"result": AddressSerializer(address).data})
