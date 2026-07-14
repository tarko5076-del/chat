from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from .models import MenuItem


class MenuItemViewSetTest(APITestCase):
    def setUp(self):
        self.item = MenuItem.objects.create(
            name="Test Pizza",
            description="A delicious test pizza",
            price=Decimal("12.99"),
            category="Mains",
            vegetarian=True,
            vegan=False,
            spicy=False,
            available=True,
            allergens="gluten, dairy",
        )

    def test_list_menu_items(self):
        response = self.client.get("/api/items/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Test Pizza")

    def test_retrieve_menu_item(self):
        response = self.client.get(f"/api/items/{self.item.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Test Pizza")
        self.assertEqual(response.data["price"], "12.99")

    def test_menu_read_only(self):
        response = self.client.post(
            "/api/items/",
            {"name": "New", "price": "10.00", "category": "Test"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_menu_allows_any(self):
        response = self.client.get("/api/items/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_empty_menu(self):
        MenuItem.objects.all().delete()
        response = self.client.get("/api/items/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)
