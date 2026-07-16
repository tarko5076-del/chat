from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health_check(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health-check"),
    path("api/", include("users.urls")),
    path("api/users/", include("users.urls")),
    path("api/", include("menu.urls")),
    path("api/menu/", include("menu.urls")),
    path("api/", include("orders.urls")),
    path("api/", include("reservations.urls")),
    path("api/", include("payments.urls")),
    path("api/agent/", include("agent.urls")),
]
