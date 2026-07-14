from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "reservations"

router = DefaultRouter()
router.register(r"reservations", views.ReservationViewSet, basename="reservation")

urlpatterns = [
    path("", include(router.urls)),
]
