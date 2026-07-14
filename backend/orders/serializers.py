from rest_framework import serializers

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "order",
            "menu_item_id",
            "item_name",
            "quantity",
            "price",
            "line_total",
        ]
        read_only_fields = ["id", "order"]

    def get_line_total(self, obj):
        return float(obj.quantity * obj.price)


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    subtotal = serializers.SerializerMethodField()
    delivery_fee = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "customer_name",
            "customer_id",
            "email",
            "phone",
            "delivery_method",
            "delivery_address",
            "payment_method",
            "status",
            "created_at",
            "items",
            "subtotal",
            "delivery_fee",
            "total",
        ]
        read_only_fields = ["id", "status", "created_at"]

    def get_subtotal(self, obj):
        return float(obj.subtotal)

    def get_delivery_fee(self, obj):
        return float(obj.delivery_fee)

    def get_total(self, obj):
        return float(obj.total)


class OrderItemCreateSerializer(serializers.Serializer):
    menu_item_id = serializers.IntegerField()
    item_name = serializers.CharField(max_length=255)
    quantity = serializers.IntegerField(min_value=1, default=1)
    price = serializers.DecimalField(max_digits=10, decimal_places=2)


class OrderCreateSerializer(serializers.Serializer):
    customer_name = serializers.CharField(max_length=255)
    customer_id = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20)
    delivery_method = serializers.ChoiceField(choices=Order.DELIVERY_CHOICES, default="delivery")
    delivery_address = serializers.CharField(required=False, allow_blank=True, default="")
    payment_method = serializers.ChoiceField(choices=Order.PAYMENT_CHOICES, default="cash")
    items = OrderItemCreateSerializer(many=True, min_length=1)

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        order = Order.objects.create(**validated_data)
        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)
        return order
