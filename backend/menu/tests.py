from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from menu.models import MenuItem
from menu.repositories import MenuRepository
from menu.services import MenuService


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
        response = self.client.get("/api/menu/items/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Test Pizza")

    def test_retrieve_menu_item(self):
        response = self.client.get(f"/api/menu/items/{self.item.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Test Pizza")
        self.assertEqual(response.data["price"], "12.99")

    def test_menu_read_only(self):
        response = self.client.post(
            "/api/menu/items/",
            {"name": "New", "price": "10.00", "category": "Test"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_menu_allows_any(self):
        response = self.client.get("/api/menu/items/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_empty_menu(self):
        MenuItem.objects.all().delete()
        response = self.client.get("/api/menu/items/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)


class MenuRepositoryTest(TestCase):
    """Tests for the new MenuRepository methods."""

    def setUp(self):
        self.repo = MenuRepository()
        self.pizza = MenuItem.objects.create(
            name="Test Pizza",
            description="Cheesy pizza",
            price=Decimal("12.99"),
            category="Mains",
            vegetarian=True,
            vegan=False,
            spicy=False,
            available=True,
            allergens="gluten, dairy",
        )
        self.salad = MenuItem.objects.create(
            name="Garden Salad",
            description="Fresh garden vegetables",
            price=Decimal("8.99"),
            category="Starters",
            vegetarian=True,
            vegan=True,
            spicy=False,
            available=True,
            allergens="",
        )
        self.sold = MenuItem.objects.create(
            name="Sold Out Item",
            description="Not available",
            price=Decimal("5.00"),
            category="Specials",
            vegetarian=True,
            vegan=True,
            spicy=False,
            available=False,
            allergens="",
        )

    def test_get_categories(self):
        cats = self.repo.get_categories()
        self.assertIn("Mains", cats)
        self.assertIn("Starters", cats)
        # Sold out items should not appear in categories
        self.assertNotIn("Specials", cats)

    def test_get_items_by_ids(self):
        items = self.repo.get_items_by_ids([self.pizza.id, self.salad.id])
        self.assertEqual(len(items), 2)

    def test_get_items_by_ids_excludes_sold(self):
        items = self.repo.get_items_by_ids([self.pizza.id, self.sold.id])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].id, self.pizza.id)

    def test_search_by_allergens_excludes(self):
        results = self.repo.search_by_allergens("gluten")
        self.assertIn(self.salad.id, [r.id for r in results])
        self.assertNotIn(self.pizza.id, [r.id for r in results])

    def test_search_by_allergens_multiple_terms(self):
        results = self.repo.search_by_allergens("gluten, dairy")
        self.assertIn(self.salad.id, [r.id for r in results])
        self.assertNotIn(self.pizza.id, [r.id for r in results])

    def test_search_by_allergens_empty_excludes_none(self):
        results = self.repo.search_by_allergens("")
        self.assertEqual(len(results), 2)  # Both available items

    def test_search_by_dietary_vegetarian(self):
        results = self.repo.search_by_dietary_need("vegetarian")
        self.assertEqual(len(results), 2)

    def test_search_by_dietary_vegan(self):
        results = self.repo.search_by_dietary_need("vegan")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.salad.id)

    def test_search_by_dietary_gluten_free(self):
        results = self.repo.search_by_dietary_need("gluten-free")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.salad.id)


class MenuServiceTest(TestCase):
    """Tests for the new MenuService methods."""

    def setUp(self):
        self.service = MenuService()
        self.item = MenuItem.objects.create(
            name="Spicy Chicken",
            description="Very spicy chicken dish with peppers",
            price=Decimal("15.99"),
            category="Mains",
            vegetarian=False,
            vegan=False,
            spicy=True,
            available=True,
            allergens="",
        )

    def test_get_categories(self):
        cats = self.service.get_categories()
        self.assertIn("Mains", cats)

    def test_get_item_with_details(self):
        details = self.service.get_item_with_details(self.item.id)
        self.assertIsNotNone(details)
        self.assertEqual(details["name"], "Spicy Chicken")
        self.assertIn("allergens", details)
        self.assertIn("available", details)

    def test_get_item_with_details_similar(self):
        details = self.service.get_item_with_details(self.item.id, include_similar=True)
        self.assertIsNotNone(details)
        self.assertIn("similar_items", details)

    def test_get_item_with_details_not_found(self):
        details = self.service.get_item_with_details(99999)
        self.assertIsNone(details)

    def test_search_natural_spicy(self):
        results = self.service.search_natural("spicy food under $20")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.item.id)

    def test_search_natural_under_price(self):
        results = self.service.search_natural("something under $10")
        self.assertEqual(len(results), 0)
        self.item.price = Decimal("8.99")
        self.item.save()
        results = self.service.search_natural("something under $10")
        self.assertEqual(len(results), 1)

    def test_search_by_allergen(self):
        MenuItem.objects.create(
            name="Salad",
            description="Leafy greens",
            price=Decimal("5.00"),
            category="Starters",
            vegetarian=True,
            vegan=True,
            spicy=False,
            available=True,
            allergens="dairy",
        )
        results = self.service.search_by_allergen("dairy")
        self.assertNotIn("Salad", [r.name for r in results])

    def test_search_by_dietary_vegan(self):
        MenuItem.objects.create(
            name="Vegan Bowl",
            description="Plant-based bowl",
            price=Decimal("12.00"),
            category="Bowls",
            vegetarian=True,
            vegan=True,
            spicy=False,
            available=True,
            allergens="",
        )
        results = self.service.search_by_dietary("vegan")
        self.assertIn("Vegan Bowl", [r.name for r in results])
