from django.urls import path
from rest_framework.routers import DefaultRouter

from cart.views import CartViewSet

router = DefaultRouter()
router.register(r"cart", CartViewSet, basename="cart")

urlpatterns = router.urls
