from rest_framework import permissions, viewsets

from .models import MenuItem
from .serializers import MenuItemSerializer


class MenuItemViewSet(viewsets.ModelViewSet):
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer
    permission_classes = [permissions.AllowAny]
    http_method_names = ["get", "head", "options"]
