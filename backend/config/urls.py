from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health_check(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health-check"),
    path("api/users/", include("users.urls")),
    path("api/menu/", include("menu.urls")),
    path("api/", include("orders.urls")),
    path("api/", include("reservations.urls")),
    path("api/", include("payments.urls")),
    path("api/agent/", include("agent.urls")),
    path("api/cart/", include("cart.urls")),
    path("api/users/addresses/", include("users.urls_addresses")),
    path("api/users/favorites/", include("users.urls_favorites")),
]
