from rest_framework.routers import DefaultRouter

from .addresses import AddressViewSet

router = DefaultRouter()
router.register(r"", AddressViewSet, basename="address")

urlpatterns = router.urls
