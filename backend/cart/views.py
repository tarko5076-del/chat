from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import CreateModelMixin, RetrieveModelMixin, DestroyModelMixin

from cart.models import Cart
from cart.serializers import (
    CartSerializer,
    CartItemCreateSerializer,
    CartItemUpdateSerializer,
)
from cart.services import CartService, CartServiceError, MenuItemNotAvailableError


class CartViewSet(CreateModelMixin, RetrieveModelMixin, DestroyModelMixin, GenericViewSet):
    """Shopping cart management — requires authentication, scoped to the current user."""
    queryset = Cart.objects.prefetch_related("items").all()
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = CartService()

    def get_queryset(self):
        return super().get_queryset().filter(
            customer_id=str(self.request.user.id)
        )

    def create(self, request, *args, **kwargs):
        """Get or create an active cart for the current user."""
        cart = self.service.get_or_create_active_cart(str(request.user.id))
        serializer = self.get_serializer(cart)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"])
    def active(self, request):
        """Get the current active cart, or return an empty response."""
        cart = self.service.repo.get_active_cart(str(request.user.id))
        if not cart:
            return Response(
                {"detail": "No active cart."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.get_serializer(cart)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def add_item(self, request):
        """Add an item to the active cart."""
        serializer = CartItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            cart, cart_item = self.service.add_item(
                str(request.user.id),
                menu_item_id=serializer.validated_data["menu_item_id"],
                quantity=serializer.validated_data.get("quantity", 1),
                notes=serializer.validated_data.get("notes", ""),
            )
        except MenuItemNotAvailableError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except CartServiceError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result_serializer = self.get_serializer(cart)
        return Response(result_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["patch"])
    def update_item(self, request, pk=None):
        """Update item quantity (set 0 to remove)."""
        cart = self.get_object()
        item_serializer = CartItemUpdateSerializer(data=request.data)
        item_serializer.is_valid(raise_exception=True)

        menu_item_id = request.data.get("menu_item_id")
        if not menu_item_id:
            return Response(
                {"detail": "menu_item_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            self.service.update_quantity(
                str(request.user.id),
                cart.id,
                int(menu_item_id),
                item_serializer.validated_data["quantity"],
            )
        except CartServiceError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cart.refresh_from_db()
        result_serializer = self.get_serializer(cart)
        return Response(result_serializer.data)

    @action(detail=True, methods=["post"])
    def remove_item(self, request, pk=None):
        """Remove an item from the cart."""
        cart = self.get_object()
        menu_item_id = request.data.get("menu_item_id")
        if not menu_item_id:
            return Response(
                {"detail": "menu_item_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            self.service.remove_item(str(request.user.id), cart.id, int(menu_item_id))
        except CartServiceError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cart.refresh_from_db()
        result_serializer = self.get_serializer(cart)
        return Response(result_serializer.data)

    @action(detail=True, methods=["post"])
    def clear(self, request, pk=None):
        """Remove all items from the cart."""
        cart = self.get_object()
        self.service.clear_cart(str(request.user.id), cart.id)
        cart.refresh_from_db()
        result_serializer = self.get_serializer(cart)
        return Response(result_serializer.data)

    @action(detail=True, methods=["post"])
    def checkout(self, request, pk=None):
        """Mark the cart as converted (used after order creation)."""
        cart = self.get_object()
        self.service.checkout(str(request.user.id), cart.id)
        return Response({"detail": f"Cart #{cart.id} checked out."})
