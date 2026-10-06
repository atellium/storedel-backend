from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Storedel Administration"
admin.site.site_title = "Storedel Admin"
admin.site.index_title = "Dashboard"

urlpatterns = [
    path("api/", include("core.urls")),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("locations.urls")),
    path("api/", include("stores.urls")),
    path("api/", include("products.urls")),
    path("api/", include("carts.urls")),
    path("api/", include("orders.urls")),
    path("api/", include("uploads.urls")),
    path("api/", include("notifications.urls")),
    path("admin/", admin.site.urls),
]
