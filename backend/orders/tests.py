from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Order, OrderItem

User = get_user_model()


class OrderViewSetTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="TestPass123!",
        )
        self.refresh = RefreshToken.for_user(self.user)
        self.access_token = str(self.refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

        self.order = Order.objects.create(
            customer_name="Test Customer",
            customer_id="cust-123",
            email="customer@test.com",
            phone="+1234567890",
            delivery_method="delivery",
            payment_method="card",
            status="active",
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            menu_item_id=1,
            item_name="Pizza",
            quantity=2,
            price=Decimal("12.99"),
        )

    def test_list_orders(self):
        response = self.client.get("/api/orders/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_retrieve_order(self):
        response = self.client.get(f"/api/orders/{self.order.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["customer_name"], "Test Customer")
        self.assertIn("items", response.data)

    def test_create_order(self):
        data = {
            "customer_name": "New Customer",
            "email": "new@test.com",
            "phone": "+0987654321",
            "delivery_method": "pickup",
            "payment_method": "cash",
            "items": [
                {"menu_item_id": 1, "item_name": "Burger", "quantity": 1, "price": "8.99"}
            ],
        }
        response = self.client.post("/api/orders/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Order.objects.count(), 2)
        self.assertEqual(OrderItem.objects.count(), 2)

    def test_create_order_empty_items(self):
        data = {
            "customer_name": "New Customer",
            "email": "new@test.com",
            "phone": "+0987654321",
            "items": [],
        }
        response = self.client.post("/api/orders/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filter_by_customer_id(self):
        response = self.client.get("/api/orders/?customer_id=cust-123")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_filter_by_status(self):
        response = self.client.get("/api/orders/?status=active")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_order_total_calculation(self):
        response = self.client.get(f"/api/orders/{self.order.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        expected_subtotal = 2 * 12.99
        expected_total = round(expected_subtotal * 1.0825 + 4.99, 2)
        self.assertAlmostEqual(response.data["subtotal"], expected_subtotal, places=2)
        self.assertAlmostEqual(response.data["total"], expected_total, places=2)
