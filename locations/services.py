from locations.models import City


def list_cities(search=None, pincode_prefix=None):
    cities = City.objects.select_related("state")
    if search:
        cities = cities.filter(name__icontains=search)
    if pincode_prefix:
        cities = cities.filter(pincode_prefixes__contains=[pincode_prefix])
    return cities.order_by("name", "pk")
