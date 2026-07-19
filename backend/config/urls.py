from django.contrib import admin
from django.urls import include, path

from config.monitoring import HealthView, MetricsView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", HealthView.as_view(), name="health-check"),
    path("metrics/", MetricsView.as_view(), name="metrics"),
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
