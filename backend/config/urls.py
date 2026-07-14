from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("users.urls")),
    path("api/", include("menu.urls")),
    path("api/", include("orders.urls")),
    path("api/", include("reservations.urls")),
    path("api/", include("payments.urls")),
    path("api/", include("agent.urls")),
]
