from rest_framework import permissions, viewsets

from reservations.cleanup import periodic_hold_cleanup
from reservations.models import Reservation
from reservations.serializers import ReservationSerializer, ReservationCreateSerializer
from reservations.services import ReservationService


class ReservationViewSet(viewsets.ModelViewSet):
    """Reservation management — requires authentication, scoped to the current user.

    Staff/admin can see all reservations. Customers see only their own.
    """
    permission_classes = [permissions.IsAuthenticated]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = ReservationService()

    def list(self, request, *args, **kwargs):
        periodic_hold_cleanup()
        return super().list(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.action == "create":
            return ReservationCreateSerializer
        return ReservationSerializer

    def get_queryset(self):
        qs = Reservation.objects.all()
        user = self.request.user

        if user.role in ("staff", "admin"):
            status_filter = self.request.query_params.get("status")
            if status_filter:
                qs = qs.filter(status=status_filter)
            return qs

        qs = qs.filter(customer_id=str(user.id))
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs
