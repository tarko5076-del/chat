from datetime import date, time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from agent.tools.order import OrderTool
from agent.tools.payment import PaymentTool
from agent.tools.reservation import ReservationTool
from agent.tools.escalation import EscalationTool
from agent.tools.search_knowledge import SearchKnowledgeTool
from menu.models import MenuItem
from orders.models import Order, OrderItem
from payments.models import Payment
from reservations.models import Reservation


class OrderToolTest(TestCase):
    def setUp(self):
        self.tool = OrderTool()
        self.menu_item = MenuItem.objects.create(
            name="Pizza Margherita",
            description="Classic tomato and mozzarella",
            category="main",
            price=Decimal("12.99"),
            available=True,
        )

    def test_create_order_with_items_and_confirmation(self):
        result = self.tool.execute(
            action="create",
            customer_name="Test",
            email="test@test.com",
            phone="+1234567890",
            delivery_method="pickup",
            payment_method="cash",
            delivery_address="",
            items=[{"menu_item_id": self.menu_item.id, "name": "Pizza", "quantity": 2, "price": "12.99"}],
            confirmed=True,
        )
        self.assertTrue(result.success)
        self.assertIn("order", result.data)

    def test_create_order_requires_confirmation(self):
        result = self.tool.execute(
            action="create",
            customer_name="Test",
            email="test@test.com",
            phone="+1234567890",
            delivery_method="pickup",
            payment_method="cash",
            delivery_address="",
            items=[{"menu_item_id": self.menu_item.id, "name": "Pizza", "quantity": 2, "price": "12.99"}],
        )
        self.assertFalse(result.success)
        self.assertEqual(result.next_action, "awaiting_confirmation")

    def test_create_order_without_items_creates_draft(self):
        result = self.tool.execute(
            action="create",
            customer_name="Test",
            email="test@test.com",
            phone="+1234567890",
        )
        self.assertTrue(result.success)
        self.assertEqual(result.data["order"]["status"], "active")

    def test_add_item_to_order(self):
        order = Order.objects.create(
            customer_name="Test",
            email="test@test.com",
            phone="+1234567890",
            status="draft",
        )
        result = self.tool.execute(
            action="add",
            order_id=order.id,
            item_name="Pizza Margherita",
            quantity=2,
        )
        self.assertTrue(result.success)
        order.refresh_from_db()
        self.assertEqual(order.items.count(), 1)

    def test_show_order(self):
        order = Order.objects.create(
            customer_name="Test",
            email="test@test.com",
            phone="+1234567890",
            status="draft",
        )
        result = self.tool.execute(
            action="show",
            order_id=order.id,
        )
        self.assertTrue(result.success)
        self.assertIn(str(order.id), result.message)

    def test_cancel_order(self):
        order = Order.objects.create(
            customer_name="Test",
            email="test@test.com",
            phone="+1234567890",
            status="draft",
        )
        result = self.tool.execute(
            action="cancel",
            order_id=order.id,
        )
        self.assertTrue(result.success)
        order.refresh_from_db()
        self.assertEqual(order.status, "cancelled")


class PaymentToolTest(TestCase):
    def setUp(self):
        self.tool = PaymentTool()
        self.order = Order.objects.create(
            customer_name="Test",
            email="test@test.com",
            phone="+1234567890",
            status="placed",
        )
        OrderItem.objects.create(
            order=self.order, menu_item_id=1, item_name="Pizza",
            quantity=1, price=Decimal("20.00"),
        )

    def test_payment_missing_fields(self):
        result = self.tool.execute()
        self.assertFalse(result.success)
        self.assertIn("order_id", result.missing_fields)

    def test_payment_invalid_method(self):
        result = self.tool.execute(
            order_id=self.order.id,
            payment_method="bitcoin",
        )
        self.assertFalse(result.success)
        self.assertIn("card", result.message)

    def test_payment_order_not_found(self):
        result = self.tool.execute(
            order_id=99999,
            payment_method="card",
        )
        self.assertFalse(result.success)

    def test_payment_without_confirmation(self):
        result = self.tool.execute(
            order_id=self.order.id,
            payment_method="card",
        )
        self.assertFalse(result.success)
        self.assertEqual(result.next_action, "awaiting_confirmation")

    def test_payment_with_confirmation(self):
        result = self.tool.execute(
            order_id=self.order.id,
            payment_method="card",
            confirmed=True,
        )
        self.assertTrue(result.success)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "paid")
        self.assertTrue(Payment.objects.filter(order=self.order, status="completed").exists())

    def test_payment_idempotency(self):
        key = "idem-key-001"
        result1 = self.tool.execute(
            order_id=self.order.id,
            payment_method="card",
            confirmed=True,
            idempotency_key=key,
        )
        self.assertTrue(result1.success)

        result2 = self.tool.execute(
            order_id=self.order.id,
            payment_method="card",
            confirmed=True,
            idempotency_key=key,
        )
        self.assertTrue(result2.success)
        self.assertIn("already processed", result2.message)


class ReservationToolTest(TestCase):
    def setUp(self):
        self.tool = ReservationTool()
        self.tomorrow = date.today() + timedelta(days=1)

    def test_check_availability(self):
        result = self.tool.execute(
            action="check",
            reservation_date=self.tomorrow.isoformat(),
            reservation_time="19:00",
            party_size=2,
        )
        self.assertTrue(result.success)
        self.assertTrue(result.data["available"])

    def test_create_reservation(self):
        result = self.tool.execute(
            action="create",
            customer_name="Test",
            phone="+1234567890",
            email="test@test.com",
            reservation_date=self.tomorrow.isoformat(),
            reservation_time="19:00",
            party_size=4,
        )
        self.assertTrue(result.success)
        self.assertIn("held", result.message.lower())
        reservation = Reservation.objects.latest("id")
        self.assertEqual(reservation.status, "held")
        self.assertIsNotNone(reservation.held_until)

    def test_create_reservation_missing_fields(self):
        result = self.tool.execute(action="create")
        self.assertFalse(result.success)

    def test_confirm_reservation(self):
        reservation = Reservation.objects.create(
            customer_name="Test",
            phone="+1234567890",
            email="test@test.com",
            reservation_date=self.tomorrow,
            reservation_time=time(19, 0),
            party_size=4,
            status="held",
            held_until=timezone.now() + timedelta(minutes=10),
        )
        result = self.tool.execute(
            action="confirm",
            reservation_id=reservation.id,
        )
        self.assertTrue(result.success)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, "confirmed")

    def test_confirm_expired_reservation(self):
        reservation = Reservation.objects.create(
            customer_name="Test",
            phone="+1234567890",
            email="test@test.com",
            reservation_date=self.tomorrow,
            reservation_time=time(19, 0),
            party_size=4,
            status="held",
            held_until=timezone.now() - timedelta(minutes=1),
        )
        result = self.tool.execute(
            action="confirm",
            reservation_id=reservation.id,
        )
        self.assertFalse(result.success)
        self.assertIn("expired", result.message.lower())

    def test_cancel_reservation(self):
        reservation = Reservation.objects.create(
            customer_name="Test",
            phone="+1234567890",
            email="test@test.com",
            reservation_date=self.tomorrow,
            reservation_time=time(19, 0),
            party_size=4,
            status="confirmed",
        )
        result = self.tool.execute(
            action="cancel",
            reservation_id=reservation.id,
        )
        self.assertTrue(result.success)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, "cancelled")

    def test_reservation_not_found(self):
        result = self.tool.execute(
            action="confirm",
            reservation_id=99999,
        )
        self.assertFalse(result.success)


class EscalationToolTest(TestCase):
    def setUp(self):
        self.tool = EscalationTool()

    def test_escalation_success(self):
        result = self.tool.execute(
            reason="Guest is frustrated",
            priority="high",
        )
        self.assertTrue(result.success)
        self.assertIn("staff", result.message.lower())


class SearchKnowledgeToolTest(TestCase):
    def setUp(self):
        self.tool = SearchKnowledgeTool()

    def test_search_empty_query(self):
        result = self.tool.execute(query="")
        self.assertFalse(result.success)
        self.assertIn("query", result.missing_fields)
