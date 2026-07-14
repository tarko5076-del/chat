from rest_framework import serializers

from orders.models import Order

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source="order.id", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "order_id",
            "provider",
            "amount",
            "status",
            "transaction_ref",
            "idempotency_key",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "transaction_ref",
            "created_at",
        ]


class PaymentCreateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    provider = serializers.ChoiceField(choices=Payment.PROVIDER_CHOICES)
    idempotency_key = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=None,
    )

    def validate_order_id(self, value):
        try:
            order = Order.objects.get(id=value)
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order not found.")

        if Payment.objects.filter(order=order, status="completed").exists():
            raise serializers.ValidationError("This order has already been paid.")

        if Payment.objects.filter(order=order, status="pending").exists():
            raise serializers.ValidationError(
                "A pending payment already exists for this order."
            )

        return value

    def validate(self, data):
        idempotency_key = data.get("idempotency_key")
        if idempotency_key:
            existing = Payment.objects.filter(
                idempotency_key=idempotency_key
            ).first()
            if existing:
                raise serializers.ValidationError(
                    {"idempotency_key": "Duplicate idempotency key."}
                )
        return data

    def create(self, validated_data):
        order = Order.objects.get(id=validated_data["order_id"])
        payment = Payment.objects.create(
            order=order,
            provider=validated_data["provider"],
            amount=order.total,
            idempotency_key=validated_data.get("idempotency_key"),
        )
        return payment
