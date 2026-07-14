from rest_framework import permissions, viewsets

from .cleanup import periodic_hold_cleanup
from .models import Reservation
from .serializers import ReservationSerializer, ReservationCreateSerializer


class ReservationViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.all()
    permission_classes = [permissions.AllowAny]

    def list(self, request, *args, **kwargs):
        periodic_hold_cleanup()
        return super().list(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.action == "create":
            return ReservationCreateSerializer
        return ReservationSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        customer_id = self.request.query_params.get("customer_id")
        status_filter = self.request.query_params.get("status")
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs
