from rest_framework import serializers

from .models import (
    MAX_PARTY_SIZE,
    OPENING_HOUR,
    CLOSING_HOUR,
    Reservation,
)


class ReservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = [
            "id",
            "customer_name",
            "customer_id",
            "phone",
            "email",
            "reservation_date",
            "reservation_time",
            "party_size",
            "status",
            "held_until",
            "created_at",
        ]
        read_only_fields = ["id", "status", "held_until", "created_at"]


class ReservationCreateSerializer(serializers.Serializer):
    customer_name = serializers.CharField(max_length=255)
    customer_id = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField()
    reservation_date = serializers.DateField()
    reservation_time = serializers.TimeField()
    party_size = serializers.IntegerField(min_value=1, max_value=MAX_PARTY_SIZE)

    def validate_reservation_time(self, value):
        hour = value.hour
        if hour < OPENING_HOUR or hour >= CLOSING_HOUR:
            raise serializers.ValidationError(
                f"Reservations are only available between {OPENING_HOUR:02d}:00 and {CLOSING_HOUR:02d}:00."
            )
        return value

    def validate(self, data):
        date = data["reservation_date"]
        time = data["reservation_time"]
        party_size = data["party_size"]

        if date < timezone.now().date():
            raise serializers.ValidationError({"reservation_date": "Cannot make reservations in the past."})

        count = Reservation.objects.filter(
            reservation_date=date,
            reservation_time=time,
            status__in=["held", "confirmed", "seated"],
        ).count()

        if count >= MAX_RESERVATIONS_PER_SLOT:
            raise serializers.ValidationError(
                {"reservation_time": "This time slot is fully booked."}
            )

        return data

    def create(self, validated_data):
        return Reservation.objects.create(**validated_data)
