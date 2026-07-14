from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from orders.models import Order, OrderItem
from .models import Payment


class PaymentViewSetTest(APITestCase):
    def setUp(self):
        self.order = Order.objects.create(
            customer_name="Test Customer",
            customer_id="cust-123",
            email="test@test.com",
            phone="+1234567890",
            delivery_method="delivery",
            payment_method="card",
            status="active",
        )
        OrderItem.objects.create(
            order=self.order,
            menu_item_id=1,
            item_name="Pizza",
            quantity=1,
            price=Decimal("12.99"),
        )

    def test_create_payment(self):
        data = {
            "order_id": self.order.id,
            "provider": "card",
            "idempotency_key": "key-001",
        }
        response = self.client.post("/api/payments/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(response.data["provider"], "card")

    def test_create_payment_duplicate_idempotency_key(self):
        Payment.objects.create(
            order=self.order,
            provider="card",
            amount=self.order.total,
            idempotency_key="key-001",
        )
        data = {
            "order_id": self.order.id,
            "provider": "card",
            "idempotency_key": "key-001",
        }
        response = self.client.post("/api/payments/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_payment_already_paid(self):
        Payment.objects.create(
            order=self.order,
            provider="card",
            amount=self.order.total,
            status="completed",
        )
        data = {
            "order_id": self.order.id,
            "provider": "card",
        }
        response = self.client.post("/api/payments/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_payment_pending_exists(self):
        Payment.objects.create(
            order=self.order,
            provider="card",
            amount=self.order.total,
            status="pending",
        )
        data = {
            "order_id": self.order.id,
            "provider": "card",
        }
        response = self.client.post("/api/payments/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_payment(self):
        payment = Payment.objects.create(
            order=self.order,
            provider="card",
            amount=self.order.total,
            status="pending",
        )
        response = self.client.post(f"/api/payments/{payment.id}/confirm/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "completed")

    def test_confirm_already_completed(self):
        payment = Payment.objects.create(
            order=self.order,
            provider="card",
            amount=self.order.total,
            status="completed",
        )
        response = self.client.post(f"/api/payments/{payment.id}/confirm/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_fail_payment(self):
        payment = Payment.objects.create(
            order=self.order,
            provider="card",
            amount=self.order.total,
            status="pending",
        )
        response = self.client.post(f"/api/payments/{payment.id}/fail/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "failed")

    def test_fail_already_completed(self):
        payment = Payment.objects.create(
            order=self.order,
            provider="card",
            amount=self.order.total,
            status="completed",
        )
        response = self.client.post(f"/api/payments/{payment.id}/fail/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_payments(self):
        Payment.objects.create(
            order=self.order,
            provider="card",
            amount=self.order.total,
        )
        response = self.client.get("/api/payments/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_filter_by_status(self):
        Payment.objects.create(
            order=self.order,
            provider="card",
            amount=self.order.total,
            status="completed",
        )
        response = self.client.get("/api/payments/?status=completed")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
