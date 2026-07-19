from django.db import models
from rest_framework import permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from menu.models import MenuItem


# ── Model ──────────────────────────────────────────────────────────────────

class Favorite(models.Model):
    """Customer's favorite menu item."""

    SOURCE_CHOICES = [
        ("explicit", "Explicit — user directly requested"),
        ("implicit", "Implicit — inferred from behavior"),
    ]

    customer_id = models.CharField(max_length=255, db_index=True)
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="explicit")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "favorites"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer_id", "menu_item"],
                name="unique_customer_menu_item_favorite",
            ),
        ]
        indexes = [
            models.Index(fields=["customer_id", "created_at"]),
        ]

    def __str__(self):
        return f"Favorite: {self.menu_item.name} ({self.customer_id})"


# ── Repository ─────────────────────────────────────────────────────────────

class FavoriteRepository:
    def list_by_customer(self, customer_id: str) -> list[Favorite]:
        return list(
            Favorite.objects.select_related("menu_item")
            .filter(customer_id=customer_id)
            .order_by("-created_at")
        )

    def get_by_menu_item(self, customer_id: str, menu_item_id: int) -> Favorite | None:
        return Favorite.objects.filter(
            customer_id=customer_id, menu_item_id=menu_item_id
        ).first()

    def create(self, *, customer_id: str, menu_item: MenuItem, source: str = "explicit") -> Favorite:
        return Favorite.objects.create(
            customer_id=customer_id, menu_item=menu_item, source=source
        )

    def delete(self, favorite: Favorite) -> None:
        favorite.delete()

    def delete_by_menu_item(self, customer_id: str, menu_item_id: int) -> bool:
        count, _ = Favorite.objects.filter(
            customer_id=customer_id, menu_item_id=menu_item_id
        ).delete()
        return count > 0


# ── Service ────────────────────────────────────────────────────────────────

class FavoriteService:
    def __init__(self):
        self.repo = FavoriteRepository()

    def get_favorites(self, customer_id: str) -> list[Favorite]:
        return self.repo.list_by_customer(customer_id)

    def add_favorite(self, customer_id: str, menu_item: MenuItem, source: str = "explicit") -> Favorite:
        existing = self.repo.get_by_menu_item(customer_id, menu_item.id)
        if existing:
            return existing
        return self.repo.create(customer_id=customer_id, menu_item=menu_item, source=source)

    def remove_favorite(self, customer_id: str, menu_item_id: int) -> bool:
        return self.repo.delete_by_menu_item(customer_id, menu_item_id)


# ── Serializers ────────────────────────────────────────────────────────────

class FavoriteSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.CharField(source="menu_item.name", read_only=True)
    menu_item_price = serializers.DecimalField(
        source="menu_item.price", max_digits=10, decimal_places=2, read_only=True
    )
    menu_item_category = serializers.CharField(source="menu_item.category", read_only=True)

    class Meta:
        model = Favorite
        fields = [
            "id", "customer_id", "menu_item", "menu_item_name",
            "menu_item_price", "menu_item_category", "source", "created_at",
        ]
        read_only_fields = ["id", "customer_id", "created_at"]


class FavoriteCreateSerializer(serializers.Serializer):
    menu_item_id = serializers.IntegerField()
    source = serializers.ChoiceField(choices=["explicit", "implicit"], default="explicit")


# ── Views ──────────────────────────────────────────────────────────────────

class FavoriteViewSet(viewsets.ModelViewSet):
    queryset = Favorite.objects.select_related("menu_item").all()
    serializer_class = FavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = FavoriteService()

    def get_queryset(self):
        return super().get_queryset().filter(customer_id=str(self.request.user.id))

    def create(self, request, *args, **kwargs):
        serializer = FavoriteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        menu_item_id = serializer.validated_data["menu_item_id"]
        try:
            menu_item = MenuItem.objects.get(id=menu_item_id)
        except MenuItem.DoesNotExist:
            return Response(
                {"detail": f"Menu item #{menu_item_id} not found."},
                status=404,
            )

        favorite = self.service.add_favorite(
            str(request.user.id),
            menu_item,
            source=serializer.validated_data.get("source", "explicit"),
        )

        result_serializer = self.get_serializer(favorite)
        return Response(result_serializer.data, status=201)

    @action(detail=False, methods=["delete"])
    def remove(self, request):
        """Remove a favorite by menu_item_id."""
        menu_item_id = request.data.get("menu_item_id") or request.query_params.get("menu_item_id")
        if not menu_item_id:
            return Response(
                {"detail": "menu_item_id is required."},
                status=400,
            )
        removed = self.service.remove_favorite(str(request.user.id), int(menu_item_id))
        if not removed:
            return Response(
                {"detail": "Favorite not found."},
                status=404,
            )
        return Response(status=204)
