from rest_framework.routers import DefaultRouter

from .favorites import FavoriteViewSet

router = DefaultRouter()
router.register(r"", FavoriteViewSet, basename="favorite")

urlpatterns = router.urls
