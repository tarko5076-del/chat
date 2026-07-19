from decimal import Decimal

from rest_framework import serializers

from cart.models import Cart, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id", "cart", "menu_item_id", "item_name",
            "quantity", "unit_price", "notes", "line_total",
        ]
        read_only_fields = ["id", "item_name", "unit_price", "line_total"]

    def get_line_total(self, obj):
        return float(obj.quantity * obj.unit_price)


class CartItemCreateSerializer(serializers.Serializer):
    menu_item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class CartItemUpdateSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=0)


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    item_count = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            "id", "customer_id", "status",
            "items", "item_count", "subtotal",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "customer_id", "status", "created_at", "updated_at"]

    def get_item_count(self, obj):
        return obj.items.count()

    def get_subtotal(self, obj):
        return float(sum(
            Decimal(str(item.unit_price)) * item.quantity
            for item in obj.items.all()
        ))
