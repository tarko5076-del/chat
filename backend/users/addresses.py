from django.db import models
from rest_framework import permissions, serializers, viewsets
from rest_framework.response import Response


# ── Model ──────────────────────────────────────────────────────────────────

class Address(models.Model):
    """Customer delivery address."""

    customer_id = models.CharField(max_length=255, db_index=True)
    label = models.CharField(max_length=100, blank=True, default="")
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    zip_code = models.CharField(max_length=20, blank=True, default="")
    country = models.CharField(max_length=100, default="Ethiopia")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "addresses"
        ordering = ["-is_default", "-updated_at"]
        indexes = [
            models.Index(fields=["customer_id", "is_default"]),
        ]

    def __str__(self):
        return f"{self.label or 'Address'} #{self.id} — {self.address_line_1}"


# ── Repository ─────────────────────────────────────────────────────────────

class AddressRepository:
    def get_by_id(self, address_id: int, customer_id: str | None = None) -> Address | None:
        qs = Address.objects.all()
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        return qs.filter(id=address_id).first()

    def list_by_customer(self, customer_id: str) -> list[Address]:
        return list(Address.objects.filter(customer_id=customer_id).order_by("-is_default", "-updated_at"))

    def get_default(self, customer_id: str) -> Address | None:
        return Address.objects.filter(customer_id=customer_id, is_default=True).first()

    def create(self, *, customer_id: str, label: str = "", address_line_1: str,
               address_line_2: str = "", city: str = "", state: str = "",
               zip_code: str = "", country: str = "Ethiopia", is_default: bool = False) -> Address:
        if is_default:
            self._unset_default(customer_id)
        return Address.objects.create(
            customer_id=customer_id, label=label, address_line_1=address_line_1,
            address_line_2=address_line_2, city=city, state=state,
            zip_code=zip_code, country=country, is_default=is_default,
        )

    def update(self, address: Address, **kwargs) -> Address:
        for key, value in kwargs.items():
            setattr(address, key, value)
        if "is_default" in kwargs and kwargs["is_default"]:
            self._unset_default(address.customer_id, exclude_id=address.id)
        address.save()
        return address

    def delete(self, address: Address) -> None:
        address.delete()

    def _unset_default(self, customer_id: str, exclude_id: int | None = None) -> None:
        qs = Address.objects.filter(customer_id=customer_id, is_default=True)
        if exclude_id:
            qs = qs.exclude(id=exclude_id)
        qs.update(is_default=False)


# ── Service ────────────────────────────────────────────────────────────────

class AddressService:
    def __init__(self):
        self.repo = AddressRepository()

    def get_addresses(self, customer_id: str) -> list[Address]:
        return self.repo.list_by_customer(customer_id)

    def get_address(self, address_id: int, customer_id: str) -> Address | None:
        return self.repo.get_by_id(address_id, customer_id=customer_id)

    def get_default(self, customer_id: str) -> Address | None:
        return self.repo.get_default(customer_id)

    def create_address(self, customer_id: str, **data) -> Address:
        return self.repo.create(customer_id=customer_id, **data)

    def update_address(self, address_id: int, customer_id: str, **data) -> Address:
        address = self.repo.get_by_id(address_id, customer_id=customer_id)
        if not address:
            raise ValueError(f"Address #{address_id} not found.")
        return self.repo.update(address, **data)

    def delete_address(self, address_id: int, customer_id: str) -> None:
        address = self.repo.get_by_id(address_id, customer_id=customer_id)
        if not address:
            raise ValueError(f"Address #{address_id} not found.")
        self.repo.delete(address)


# ── Serializers ────────────────────────────────────────────────────────────

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            "id", "customer_id", "label", "address_line_1", "address_line_2",
            "city", "state", "zip_code", "country", "is_default",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "customer_id", "created_at", "updated_at"]


class AddressCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            "label", "address_line_1", "address_line_2",
            "city", "state", "zip_code", "country", "is_default",
        ]


# ── Views ──────────────────────────────────────────────────────────────────

class AddressViewSet(viewsets.ModelViewSet):
    queryset = Address.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = AddressService()

    def get_serializer_class(self):
        if self.action == "create":
            return AddressCreateSerializer
        return AddressSerializer

    def get_queryset(self):
        return Address.objects.filter(customer_id=str(self.request.user.id))

    def list(self, request, *args, **kwargs):
        addresses = self.service.get_addresses(str(request.user.id))
        serializer = self.get_serializer(addresses, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        self.service.create_address(customer_id=str(self.request.user.id), **serializer.validated_data)
