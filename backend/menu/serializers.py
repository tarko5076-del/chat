from rest_framework import serializers

from .models import MenuItem


class MenuItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItem
        fields = [
            "id",
            "name",
            "description",
            "price",
            "category",
            "vegetarian",
            "vegan",
            "spicy",
            "available",
            "allergens",
        ]
        read_only_fields = ["id"]
