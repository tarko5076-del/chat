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
            "currency",
            "status",
            "transaction_ref",
            "chapa_tx_ref",
            "checkout_url",
            "idempotency_key",
            "customer_email",
            "customer_name",
            "failure_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "transaction_ref",
            "chapa_tx_ref",
            "checkout_url",
            "created_at",
            "updated_at",
        ]


class PaymentCreateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    provider = serializers.ChoiceField(choices=Payment.PROVIDER_CHOICES)
    customer_email = serializers.EmailField(required=False, default="")
    customer_name = serializers.CharField(max_length=255, required=False, default="")
    idempotency_key = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=None,
    )

    def validate_order_id(self, value):
        try:
            order = Order.objects.get(id=value)
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order not found.")

        existing = Payment.objects.filter(order=order).first()
        if existing:
            if existing.status == "completed":
                raise serializers.ValidationError("This order has already been paid.")
            if existing.status in ("pending", "processing"):
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
            customer_email=validated_data.get("customer_email", ""),
            customer_name=validated_data.get("customer_name", ""),
        )
        return payment
