from rest_framework import permissions, viewsets

from menu.models import MenuItem
from menu.serializers import MenuItemSerializer
from menu.services import MenuService


class MenuItemViewSet(viewsets.ModelViewSet):
    """Menu is public — no authentication required (read-only).

    The menu is the restaurant's public face, so anyone can browse it
    without logging in.
    """
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer
    permission_classes = [permissions.AllowAny]
    http_method_names = ["get", "head", "options"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = MenuService()
