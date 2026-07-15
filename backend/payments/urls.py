from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "payments"

router = DefaultRouter()
router.register(r"payments", views.PaymentViewSet, basename="payment")

urlpatterns = [
    path("", include(router.urls)),
    path("webhook/chapa/", views.chapa_webhook, name="chapa-webhook"),
]
