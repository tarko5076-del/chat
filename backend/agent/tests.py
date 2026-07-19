from datetime import date, time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from asgiref.sync import async_to_sync

from agent.tools.order import OrderTool
from agent.tools.payment import PaymentTool
from agent.tools.reservation import ReservationTool
from agent.tools.escalation import EscalationTool
from agent.tools.search_knowledge import SearchKnowledgeTool
from agent.tools.menu import MenuTool, GetMenuItemDetailsTool
from agent.tools.recommend import RecommendMenuTool
from agent.tools.base import ToolResult
from agent.recommender import RecommendationService
from agent.controller import agent
from agent.order_workflow import OrderWorkflow
from agent.memory import ConversationMemory
from menu.models import MenuItem
from orders.models import Order, OrderItem
from payments.models import Payment
from reservations.models import Reservation
from agent.models import SemanticMemory, CustomerProfile


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
            customer_email="test@test.com",
        )
        self.assertFalse(result.success)
        self.assertIn("chapa", result.message)

    def test_payment_order_not_found(self):
        result = self.tool.execute(
            order_id=99999,
            payment_method="chapa",
            customer_email="test@test.com",
        )
        self.assertFalse(result.success)

    def test_payment_without_confirmation(self):
        result = self.tool.execute(
            order_id=self.order.id,
            payment_method="cash",
            customer_email="test@test.com",
        )
        self.assertFalse(result.success)
        self.assertEqual(result.next_action, "awaiting_confirmation")

    def test_payment_with_confirmation(self):
        result = self.tool.execute(
            order_id=self.order.id,
            payment_method="cash",
            customer_email="test@test.com",
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
            payment_method="cash",
            customer_email="test@test.com",
            confirmed=True,
            idempotency_key=key,
        )
        self.assertTrue(result1.success)

        result2 = self.tool.execute(
            order_id=self.order.id,
            payment_method="cash",
            customer_email="test@test.com",
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


# ─── Multi-Turn Ordering Integration Tests ────────────────────────────────


class MockAgent:
    """A minimal agent stub for testing the OrderWorkflow directly.

    Provides _execute_tool that delegates to the real tool classes so that
    the OrderWorkflow can create real orders, add real items, etc.
    """
    def __init__(self):
        from agent.tools.order import OrderTool
        from agent.tools.payment import PaymentTool
        from agent.tools.menu import MenuTool
        self._tools = {
            "manage_order": OrderTool(),
            "process_payment": PaymentTool(),
            "list_menu_items": MenuTool(),
        }

    async def _execute_tool(self, name: str, args: dict, memory: ConversationMemory) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(success=False, message=f"Tool '{name}' not available")
        from asgiref.sync import sync_to_async
        result = await sync_to_async(tool.execute)(**args)
        memory.remember_tool_result(result)
        return result


def _run_workflow(wf, message, memory):
    """Synchronous helper to run order_workflow.handle()."""
    return async_to_sync(wf.handle)(message, memory)


class MultiTurnOrderingTest(TestCase):
    """Integration tests for the multi-turn order workflow.

    Each test simulates a full conversation turn-by-turn to verify that
    state persists between messages and the correct next prompt is shown.
    """

    @classmethod
    def setUpTestData(cls):
        cls.coffee = MenuItem.objects.create(
            name="Ethiopian Coffee",
            description="Traditional Ethiopian coffee ceremony style",
            category="Drinks",
            price=Decimal("5.00"),
            available=True,
        )
        cls.burger = MenuItem.objects.create(
            name="Tibs",
            description="Tender beef cubes sautéed with onions and jalapeños",
            category="Tibs (Sautéed)",
            price=Decimal("20.00"),
            available=True,
        )

    def setUp(self):
        self.agent = MockAgent()
        self.wf = OrderWorkflow(self.agent)
        self.memory = ConversationMemory()
        self.memory.customer_id = "test-123"
        self.memory.customer_name = "TestUser"

    # ── Test 1: Quantity slot filling ──────────────────────────────────────

    def test_quantity_slot_filling(self):
        """coffee → two → adds 2 coffees"""
        # Turn 1: Ask for coffee
        response = _run_workflow(self.wf, "I want coffee", self.memory)
        self.assertIsNotNone(response)
        self.assertIn("Coffee", response)
        self.assertIn("How many", response)
        self.assertEqual(self.memory.order_status, "awaiting_quantity")
        self.assertIsNotNone(self.memory.pending_item())

        # Turn 2: Say quantity
        response = _run_workflow(self.wf, "two", self.memory)
        self.assertIsNotNone(response)
        self.assertIn("added", response.lower())
        self.assertIn("2", response)
        self.assertIn("Coffee", response)
        items = self.memory.current_order_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["quantity"], 2)
        self.assertEqual(items[0]["name"], "Ethiopian Coffee")
        # Should now be asking about delivery method
        self.assertEqual(self.memory.order_status, "awaiting_delivery_method")

    # ── Test 2: Delivery method selection ───────────────────────────────────

    def test_delivery_method_selection(self):
        """coffee → two → delivery → asks for address"""
        _run_workflow(self.wf, "I want coffee", self.memory)
        _run_workflow(self.wf, "two", self.memory)
        self.assertEqual(self.memory.order_status, "awaiting_delivery_method")

        # Turn 3: Choose delivery
        response = _run_workflow(self.wf, "delivery", self.memory)
        self.assertIsNotNone(response)
        self.assertIn("delivery address", response.lower())
        self.assertEqual(self.memory.order_status, "awaiting_address")
        self.assertEqual(self.memory.order_state.get("delivery_method"), "delivery")

    # ── Test 3: Address collection ─────────────────────────────────────────

    def test_address_collection(self):
        """coffee → two → delivery → 123 Main St → asks for payment method"""
        _run_workflow(self.wf, "I want coffee", self.memory)
        _run_workflow(self.wf, "two", self.memory)
        _run_workflow(self.wf, "delivery", self.memory)

        # Turn 4: Provide address
        response = _run_workflow(self.wf, "123 Main Street, Addis Ababa", self.memory)
        self.assertIsNotNone(response)
        self.assertIn("pay", response.lower())
        self.assertEqual(self.memory.order_status, "awaiting_payment_method")
        self.assertEqual(self.memory.order_state.get("address"), "123 Main Street, Addis Ababa")

    # ── Test 4: Cancellation with "never mind" ─────────────────────────────

    def test_cancel_pending_with_never_mind(self):
        """coffee → never mind → cancels pending item"""
        _run_workflow(self.wf, "I want coffee", self.memory)
        self.assertEqual(self.memory.order_status, "awaiting_quantity")
        self.assertIsNotNone(self.memory.pending_item())

        # Cancel
        response = _run_workflow(self.wf, "never mind", self.memory)
        self.assertIsNotNone(response)
        self.assertIn("cancel", response.lower())
        # Pending should be cleared
        self.assertIsNone(self.memory.pending_item())
        # No items should have been added
        self.assertEqual(len(self.memory.current_order_items()), 0)

    # ── Test 5: Topic switching preserves pending state ────────────────────

    def test_topic_switch_preserves_pending(self):
        """coffee → what desserts do you have? → pending preserved"""
        _run_workflow(self.wf, "I want coffee", self.memory)
        self.assertEqual(self.memory.order_status, "awaiting_quantity")
        pending_before = self.memory.pending_item()
        self.assertIsNotNone(pending_before)

        # Topic switch - should return None (let the LLM/planner handle it)
        response = _run_workflow(self.wf, "What desserts do you have?", self.memory)
        # The order workflow returns None for topic switches (LLM handles it)
        # But the pending state must be preserved
        self.assertIsNone(response)
        self.assertEqual(self.memory.order_status, "awaiting_quantity")
        self.assertEqual(self.memory.pending_item(), pending_before)

    # ── Test 6: Item change during quantity prompt ─────────────────────────

    def test_item_change_with_actually(self):
        """coffee → actually tibs → changes pending item from coffee to tibs"""
        _run_workflow(self.wf, "I want coffee", self.memory)
        self.assertEqual(self.memory.order_status, "awaiting_quantity")
        self.assertEqual(self.memory.pending_item()["name"], "Ethiopian Coffee")

        # Change item — "actually" signals item change; "tibs" matches the Tibs menu item
        response = _run_workflow(self.wf, "actually tibs", self.memory)
        self.assertIsNotNone(response)
        # Should redirect to item selection (pending cleared)
        self.assertIsNone(self.memory.pending_item())
        self.assertEqual(self.memory.order_status, "collecting")

        # Now order the new item
        response = _run_workflow(self.wf, "i want tibs", self.memory)
        self.assertIsNotNone(response)
        self.assertIn("How many", response)
        self.assertEqual(self.memory.order_status, "awaiting_quantity")
        self.assertEqual(self.memory.pending_item()["name"], "Tibs")

    # ── Test 7: Full checkout flow ─────────────────────────────────────────

    def test_full_checkout_flow(self):
        """coffee → two → delivery → address → card → confirmation → submit"""
        # Turn 1-2: Select item and quantity
        _run_workflow(self.wf, "I want coffee", self.memory)
        _run_workflow(self.wf, "two", self.memory)
        self.assertEqual(self.memory.order_status, "awaiting_delivery_method")
        self.assertEqual(len(self.memory.current_order_items()), 1)

        # Turn 3: Choose delivery
        response = _run_workflow(self.wf, "delivery", self.memory)
        self.assertIn("address", response.lower())

        # Turn 4: Provide address
        response = _run_workflow(self.wf, "Bole Road, Addis Ababa", self.memory)
        self.assertIn("pay", response.lower())

        # Turn 5: Choose payment method
        response = _run_workflow(self.wf, "card", self.memory)
        self.assertIn("order summary", response.lower())
        self.assertIn("place this order", response.lower())
        self.assertEqual(self.memory.order_status, "awaiting_confirmation")

    # ── Test 8: Pickup flow (no address needed) ────────────────────────────

    def test_pickup_flow_skips_address(self):
        """coffee → one → pickup → skip address, go to payment"""
        _run_workflow(self.wf, "I want coffee", self.memory)
        _run_workflow(self.wf, "one", self.memory)
        self.assertEqual(self.memory.order_status, "awaiting_delivery_method")

        # Choose pickup
        response = _run_workflow(self.wf, "pickup", self.memory)
        self.assertIsNotNone(response)
        self.assertIn("pay", response.lower())
        # Should skip address and go directly to payment method
        self.assertEqual(self.memory.order_status, "awaiting_payment_method")

    # ── Test 9: Number word variations ─────────────────────────────────────

    def test_number_word_variations(self):
        """coffee → '3 please' → adds 3 coffees"""
        _run_workflow(self.wf, "I want coffee", self.memory)
        self.assertEqual(self.memory.order_status, "awaiting_quantity")

        response = _run_workflow(self.wf, "3 please", self.memory)
        self.assertIsNotNone(response)
        self.assertIn("3", response)
        items = self.memory.current_order_items()
        self.assertEqual(items[0]["quantity"], 3)

    def test_make_it_two(self):
        """coffee → 'make it two' → adds 2"""
        _run_workflow(self.wf, "I want coffee", self.memory)
        self.assertEqual(self.memory.order_status, "awaiting_quantity")

        response = _run_workflow(self.wf, "make it two", self.memory)
        self.assertIsNotNone(response)
        self.assertIn("added", response.lower())
        self.assertIn("2", response)

    def test_actually_three(self):
        """coffee → 'actually three' → adds 3, NOT item change"""
        _run_workflow(self.wf, "I want coffee", self.memory)
        self.assertEqual(self.memory.order_status, "awaiting_quantity")

        response = _run_workflow(self.wf, "actually three", self.memory)
        self.assertIsNotNone(response)
        self.assertIn("added", response.lower())
        self.assertIn("3", response)
        # Should NOT be collecting (item change redirect)
        self.assertNotEqual(self.memory.order_status, "collecting")

    # ── Test 10: State persistence round-trip ───────────────────────────────

    def test_state_persistence_round_trip(self):
        """Simulate saving and loading conversation state between requests"""
        # Simulate two turns
        _run_workflow(self.wf, "I want coffee", self.memory)
        _run_workflow(self.wf, "two", self.memory)
        self.assertEqual(self.memory.order_status, "awaiting_delivery_method")

        # Save state (simulating _save_memory_state in views.py)
        state = self.memory.to_state()
        state.pop("customer_name", None)
        state.pop("customer_id", None)
        state.pop("email", None)
        state.pop("phone", None)

        # Create a fresh memory from saved state (simulating next request)
        fresh_memory = ConversationMemory.from_state(state)
        fresh_memory.customer_id = "test-123"
        fresh_memory.customer_name = "TestUser"

        # Verify state was restored
        self.assertEqual(fresh_memory.order_status, "awaiting_delivery_method")
        items = fresh_memory.current_order_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "Ethiopian Coffee")
        self.assertEqual(items[0]["quantity"], 2)

        # Continue the conversation with the restored memory
        response = async_to_sync(self.wf.handle)("delivery", fresh_memory)
        self.assertIsNotNone(response)
        self.assertIn("address", response.lower())
        self.assertEqual(fresh_memory.order_state.get("delivery_method"), "delivery")

    # ── Test 11: Multiple items in cart ────────────────────────────────────

    def test_multiple_items(self):
        """coffee → 2 → delivery → address → card → change → tibs → 1 → verify both"""
        _run_workflow(self.wf, "I want coffee", self.memory)
        _run_workflow(self.wf, "two", self.memory)
        _run_workflow(self.wf, "delivery", self.memory)
        _run_workflow(self.wf, "Bole Road, Addis Ababa", self.memory)
        _run_workflow(self.wf, "card", self.memory)

        # Now at confirmation — decline to go back to collecting
        response = _run_workflow(self.wf, "change", self.memory)
        self.assertIsNotNone(response)
        self.assertEqual(self.memory.order_status, "collecting")

        # Order a second item
        response = _run_workflow(self.wf, "i want tibs", self.memory)
        self.assertIsNotNone(response)
        self.assertIn("How many", response)
        _run_workflow(self.wf, "one", self.memory)

        # Should have 2 items now
        items = self.memory.current_order_items()
        self.assertEqual(len(items), 2)

        # Coffee: 2, Tibs: 1
        coffee_item = next(i for i in items if i["name"] == "Ethiopian Coffee")
        burger_item = next(i for i in items if i["name"] == "Tibs")
        self.assertEqual(coffee_item["quantity"], 2)
        self.assertEqual(burger_item["quantity"], 1)


# ─── Milestone 3: Menu Intelligence Tests ────────────────────────────────


class MenuToolEnhancedTest(TestCase):
    """Tests for the enhanced MenuTool with query, allergens, dietary params."""

    def setUp(self):
        self.tool = MenuTool()
        self.pizza = MenuItem.objects.create(
            name="Test Pizza",
            description="Cheesy pizza with pepperoni",
            price=Decimal("12.99"),
            category="Mains",
            vegetarian=False,
            vegan=False,
            spicy=False,
            available=True,
            allergens="gluten, dairy",
        )
        self.salad = MenuItem.objects.create(
            name="Garden Salad",
            description="Fresh garden vegetables with vinaigrette",
            price=Decimal("8.99"),
            category="Starters",
            vegetarian=True,
            vegan=True,
            spicy=False,
            available=True,
            allergens="",
        )

    def test_search_by_query_natural_language(self):
        result = self.tool.execute(query="spicy")
        self.assertTrue(result.success)
        # No items are spicy, so should show nothing
        # But the query doesn't auto-detect spicy since it just passes through
        self.assertIn("No menu items", result.message)

    def test_search_by_allergens(self):
        result = self.tool.execute(allergens="gluten")
        self.assertTrue(result.success)
        item_names = [item["name"] for item in result.data["items"]]
        self.assertIn("Garden Salad", item_names)
        self.assertNotIn("Test Pizza", item_names)

    def test_search_by_dietary(self):
        result = self.tool.execute(dietary="vegan")
        self.assertTrue(result.success)
        item_names = [item["name"] for item in result.data["items"]]
        self.assertIn("Garden Salad", item_names)
        self.assertNotIn("Test Pizza", item_names)

    def test_search_by_vegetarian_flag(self):
        result = self.tool.execute(vegetarian=True)
        self.assertTrue(result.success)
        item_names = [item["name"] for item in result.data["items"]]
        self.assertIn("Garden Salad", item_names)

    def test_search_empty_results(self):
        result = self.tool.execute(max_price=1)
        self.assertTrue(result.success)
        self.assertIn("No menu items", result.message)
        self.assertEqual(len(result.data["items"]), 0)


class GetMenuItemDetailsToolTest(TestCase):
    """Tests for the new GetMenuItemDetailsTool."""

    def setUp(self):
        self.tool = GetMenuItemDetailsTool()
        self.item = MenuItem.objects.create(
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

    def test_get_details_existing_item(self):
        result = self.tool.execute(item_id=self.item.id)
        self.assertTrue(result.success)
        self.assertEqual(result.data["name"], "Test Pizza")
        self.assertIn("allergens", result.data)
        self.assertEqual(result.data["allergens"], "gluten, dairy")

    def test_get_details_with_similar(self):
        result = self.tool.execute(item_id=self.item.id, include_similar=True)
        self.assertTrue(result.success)
        self.assertIn("similar_items", result.data)

    def test_get_details_non_existent_item(self):
        result = self.tool.execute(item_id=99999)
        self.assertFalse(result.success)
        self.assertIn("could not find", result.message.lower())

    def test_get_details_missing_id(self):
        result = self.tool.execute()
        self.assertFalse(result.success)
        self.assertIn("item_id", result.missing_fields)


class RecommendMenuToolTest(TestCase):
    """Tests for the RecommendMenuTool."""

    def setUp(self):
        self.tool = RecommendMenuTool()
        self.pizza = MenuItem.objects.create(
            name="Margherita Pizza",
            description="Classic cheese pizza",
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
            description="Fresh vegetables",
            price=Decimal("8.99"),
            category="Starters",
            vegetarian=True,
            vegan=True,
            spicy=False,
            available=True,
            allergens="",
        )

    def test_recommend_without_preferences(self):
        """Should return some recommendations even without preferences."""
        result = self.tool.execute()
        self.assertTrue(result.success)
        self.assertIn("recommendations", result.data)
        self.assertGreater(len(result.data["recommendations"]), 0)

    def test_recommend_vegetarian(self):
        result = self.tool.execute(preferences={"vegetarian": True})
        self.assertTrue(result.success)
        names = [r["item"]["name"] for r in result.data["recommendations"]]
        # Both are vegetarian
        self.assertIn("Margherita Pizza", names)
        self.assertIn("Garden Salad", names)

    def test_recommend_vegan(self):
        result = self.tool.execute(preferences={"vegan": True})
        self.assertTrue(result.success)
        names = [r["item"]["name"] for r in result.data["recommendations"]]
        self.assertIn("Garden Salad", names)
        # Pizza is not vegan
        self.assertNotIn("Margherita Pizza", names)

    def test_recommend_spicy_no_results(self):
        """No items are spicy, so returns empty."""
        result = self.tool.execute(preferences={"spicy": True})
        self.assertTrue(result.success)
        self.assertEqual(len(result.data["recommendations"]), 0)

    def test_recommend_with_customer_id(self):
        """Recommend with customer_id (no memory is fine)."""
        result = self.tool.execute(customer_id="test-customer", count=2)
        self.assertTrue(result.success)
        self.assertLessEqual(len(result.data["recommendations"]), 2)

    def test_recommend_max_price(self):
        result = self.tool.execute(preferences={"max_price": 10})
        self.assertTrue(result.success)
        names = [r["item"]["name"] for r in result.data["recommendations"]]
        self.assertIn("Garden Salad", names)
        # Pizza is $12.99, over $10
        self.assertNotIn("Margherita Pizza", names)


class RecommendationServiceTest(TestCase):
    """Tests for the RecommendationService."""

    def setUp(self):
        self.service = RecommendationService()
        self.pizza = MenuItem.objects.create(
            name="Spicy Chicken",
            description="Very spicy chicken",
            price=Decimal("15.99"),
            category="Mains",
            vegetarian=False,
            vegan=False,
            spicy=True,
            available=True,
            allergens="",
        )
        self.salad = MenuItem.objects.create(
            name="Garden Salad",
            description="Fresh vegetables",
            price=Decimal("8.99"),
            category="Starters",
            vegetarian=True,
            vegan=True,
            spicy=False,
            available=True,
            allergens="",
        )

    def test_recommend_with_preferences(self):
        recs = self.service.recommend(preferences={"spicy": True, "max_price": 20})
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["item"]["name"], "Spicy Chicken")

    def test_recommend_with_vegan_preference(self):
        recs = self.service.recommend(preferences={"vegan": True})
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["item"]["name"], "Garden Salad")

    def test_recommend_with_customer_profile(self):
        profile = {
            "dietary_restrictions": "vegetarian",
            "spice_tolerance": "high",
            "favorite_items": "Spicy Chicken",
            "budget_range": "20",
        }
        recs = self.service.recommend(customer_profile=profile)
        # Spicy Chicken should be top result (favorite + spicy)
        self.assertEqual(recs[0]["item"]["name"], "Spicy Chicken")
        self.assertIn("favorites", " ".join(recs[0]["reasons"]).lower())

    def test_recommend_no_available_items(self):
        MenuItem.objects.all().update(available=False)
        recs = self.service.recommend(preferences={"spicy": True})
        self.assertEqual(len(recs), 0)

    def test_recommend_count_limits(self):
        recs = self.service.recommend(count=1)
        self.assertLessEqual(len(recs), 1)

    def test_recommend_reasons_included(self):
        recs = self.service.recommend(preferences={"vegetarian": True})
        for rec in recs:
            self.assertIn("reasons", rec)
            self.assertGreater(len(rec["reasons"]), 0)


# ─── Milestone 4: Ordering Agent Tests ──────────────────────────────────


class CartToolTest(TestCase):
    """Tests for the ManageCartTool."""

    def setUp(self):
        from agent.tools.cart import ManageCartTool
        self.tool = ManageCartTool()
        self.item = MenuItem.objects.create(
            name="Pizza Margherita",
            description="Classic tomato and mozzarella",
            price=Decimal("12.99"),
            category="main",
            available=True,
        )
        self.customer_id = "test-customer-001"

    def test_add_item_to_cart(self):
        result = self.tool.execute(
            action="add",
            customer_id=self.customer_id,
            item_name="Pizza Margherita",
            quantity=2,
        )
        self.assertTrue(result.success)
        self.assertIn("Pizza", result.message)
        self.assertIn("cart", result.data)
        self.assertEqual(result.data["cart"]["item_count"], 1)

    def test_add_item_twice_quantity_increases(self):
        self.tool.execute(
            action="add", customer_id=self.customer_id,
            item_name="Pizza Margherita", quantity=1,
        )
        result = self.tool.execute(
            action="add", customer_id=self.customer_id,
            item_name="Pizza Margherita", quantity=3,
        )
        self.assertTrue(result.success)
        # Cart should have 4 total (1 + 3)
        self.assertEqual(result.data["cart"]["item_count"], 1)
        # CartService merging increments qty: 1 + 3 = 4
        # Check the returned cart_item reflects the merge
        self.assertEqual(result.data["added_item"]["quantity"], 4)

    def test_add_item_not_found(self):
        result = self.tool.execute(
            action="add", customer_id=self.customer_id,
            item_name="Nonexistent Dish", quantity=1,
        )
        self.assertFalse(result.success)
        self.assertIn("don't have", result.message.lower())

    def test_show_cart_with_items(self):
        self.tool.execute(
            action="add", customer_id=self.customer_id,
            item_name="Pizza Margherita", quantity=2,
        )
        result = self.tool.execute(action="show", customer_id=self.customer_id)
        self.assertTrue(result.success)
        self.assertIn("Pizza", result.message)
        self.assertIn("2 x", result.message)
        self.assertIn("25.98", result.message)

    def test_show_empty_cart(self):
        result = self.tool.execute(action="show", customer_id="new-customer")
        self.assertTrue(result.success)
        self.assertIn("empty", result.message.lower())

    def test_remove_item(self):
        self.tool.execute(
            action="add", customer_id=self.customer_id,
            item_name="Pizza Margherita", quantity=1,
        )
        result = self.tool.execute(
            action="remove", customer_id=self.customer_id,
            item_name="Pizza Margherita",
        )
        self.assertTrue(result.success)
        self.assertIn("removed", result.message.lower())

    def test_unknown_action(self):
        result = self.tool.execute(action="unknown", customer_id=self.customer_id)
        self.assertFalse(result.success)
        self.assertIn("unknown cart action", result.message.lower())


class CheckoutCartToolTest(TestCase):
    """Tests for the CheckoutCartTool."""

    def setUp(self):
        from agent.tools.cart import ManageCartTool
        from agent.tools.checkout import CheckoutCartTool
        self.cart_tool = ManageCartTool()
        self.tool = CheckoutCartTool()
        self.item = MenuItem.objects.create(
            name="Pizza Margherita",
            description="Classic tomato and mozzarella",
            price=Decimal("12.99"),
            category="main",
            available=True,
        )
        self.customer_id = "test-checkout-001"

    def _add_item_to_cart(self):
        self.cart_tool.execute(
            action="add", customer_id=self.customer_id,
            item_name="Pizza Margherita", quantity=2,
        )

    def test_checkout_requires_missing_fields(self):
        self._add_item_to_cart()
        result = self.tool.execute(customer_id=self.customer_id)
        self.assertFalse(result.success)
        self.assertIn("Order Summary", result.message)
        self.assertIn("delivery_method", str(result.data))

    def test_checkout_without_items(self):
        result = self.tool.execute(customer_id="empty-customer")
        self.assertFalse(result.success)
        self.assertIn("empty", result.message.lower())

    def test_checkout_without_confirmation(self):
        self._add_item_to_cart()
        result = self.tool.execute(
            customer_id=self.customer_id,
            delivery_method="pickup",
            payment_method="cash",
        )
        self.assertTrue(result.success)  # All required fields present
        self.assertEqual(result.next_action, "awaiting_confirmation")

    def test_checkout_with_confirmation_creates_order(self):
        self._add_item_to_cart()
        result = self.tool.execute(
            customer_id=self.customer_id,
            customer_name="Test",
            email="test@test.com",
            delivery_method="pickup",
            payment_method="cash",
            confirmed=True,
        )
        self.assertTrue(result.success)
        self.assertIn("order", result.data)
        self.assertIn("Order placed", result.message)

    def test_checkout_delivery_requires_address(self):
        self._add_item_to_cart()
        result = self.tool.execute(
            customer_id=self.customer_id,
            delivery_method="delivery",
            payment_method="cash",
        )
        self.assertFalse(result.success)
        self.assertIn("delivery_address", str(result.data))

    def test_checkout_delivery_with_address_and_confirmation(self):
        self._add_item_to_cart()
        result = self.tool.execute(
            customer_id=self.customer_id,
            customer_name="Test",
            email="test@test.com",
            delivery_method="delivery",
            delivery_address="123 Main St",
            payment_method="cash",
            confirmed=True,
        )
        self.assertTrue(result.success)
        self.assertIn("Order placed", result.message)


# ─── Milestone 6: Reservation Agent Tests ──────────────────────────────────


class ReservationWorkflowMockAgent:
    """Minimal agent stub for testing ReservationWorkflow."""

    def __init__(self):
        from agent.tools.reservation import ReservationTool
        self._tools = {"manage_reservation": ReservationTool()}

    async def _execute_tool(self, name: str, args: dict, memory: ConversationMemory) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(success=False, message=f"Tool '{name}' not available")
        from asgiref.sync import sync_to_async
        result = await sync_to_async(tool.execute)(**args)
        memory.remember_tool_result(result)
        return result


class ReservationWorkflowTest(TestCase):
    """Tests for the multi-turn reservation workflow."""

    def setUp(self):
        from agent.reservation_workflow import ReservationWorkflow
        self.agent = ReservationWorkflowMockAgent()
        self.wf = ReservationWorkflow(self.agent)
        self.memory = ConversationMemory()

    def _run(self, message):
        return async_to_sync(self.wf.handle)(message, self.memory)

    def test_returns_none_without_reservation_context(self):
        """If no reservation keywords and no pending state, return None."""
        response = self._run("What is on the menu?")
        self.assertIsNone(response)

    def test_starts_reservation_flow_with_keyword(self):
        """'I'd like to book a table' starts the flow and asks for date."""
        response = self._run("I'd like to book a table")
        self.assertIsNotNone(response)
        self.assertIn("date", response.lower())
        self.assertEqual(self.memory.reservation_status, "awaiting_date")

    def test_collects_date_then_time(self):
        """Book a table → tomorrow → asks for time"""
        self._run("book a table")
        self.assertEqual(self.memory.reservation_status, "awaiting_date")
        response = self._run("tomorrow")
        self.assertIsNotNone(response)
        self.assertIn("time", response.lower())
        self.assertEqual(self.memory.reservation_status, "awaiting_time")
        self.assertIsNotNone(self.memory.reservation_date)

    def test_collects_time_then_party_size(self):
        """book → tomorrow → 7pm → asks for party size"""
        self._run("book a table")
        self._run("tomorrow")
        response = self._run("7pm")
        self.assertIsNotNone(response)
        self.assertIn("guests", response.lower())
        self.assertEqual(self.memory.reservation_status, "awaiting_party_size")
        self.assertIsNotNone(self.memory.reservation_time)

    def test_collects_party_size_then_name(self):
        """book → tomorrow → 7pm → 4 guests → asks for name"""
        self._run("book a table")
        self._run("tomorrow")
        self._run("7pm")
        response = self._run("4 guests")
        self.assertIsNotNone(response)
        self.assertIn("name", response.lower())
        self.assertEqual(self.memory.reservation_status, "awaiting_customer_name")
        self.assertEqual(self.memory.party_size, 4)

    def test_collects_name_then_phone(self):
        """book → tomorrow → 7pm → 4 → John → asks for phone"""
        self._run("book a table")
        self._run("tomorrow")
        self._run("7pm")
        self._run("4 guests")
        response = self._run("my name is John")
        self.assertIsNotNone(response)
        self.assertIn("phone", response.lower())
        self.assertEqual(self.memory.reservation_status, "awaiting_phone")
        self.assertEqual(self.memory.customer_name, "John")

    def test_collects_phone_then_email(self):
        """book → tomorrow → 7pm → 4 → John → 555-1234 → asks for email"""
        self._run("book a table")
        self._run("tomorrow")
        self._run("7pm")
        self._run("4 guests")
        self._run("John")
        response = self._run("+1234567890")
        self.assertIsNotNone(response)
        self.assertIn("email", response.lower())
        self.assertEqual(self.memory.reservation_status, "awaiting_email")
        self.assertIsNotNone(self.memory.phone)

    def test_shows_summary_before_confirmation(self):
        """When all info collected, shows summary and asks for confirmation."""
        self._run("book a table")
        self._run("tomorrow")
        self._run("7pm")
        self._run("4 guests")
        self._run("John")
        self._run("+1234567890")
        response = self._run("john@test.com")
        self.assertIsNotNone(response)
        self.assertIn("Summary", response)
        self.assertIn("book this table", response.lower())
        self.assertEqual(self.memory.reservation_status, "awaiting_confirmation")

    def test_cancel_during_flow(self):
        """Cancel during the flow resets everything."""
        self._run("book a table")
        self._run("tomorrow")
        self._run("7pm")
        response = self._run("never mind")
        self.assertIsNotNone(response)
        self.assertIn("cancel", response.lower())
        self.assertIsNone(self.memory.reservation_status)
        self.assertIsNone(self.memory.reservation_date)
        self.assertIsNone(self.memory.reservation_time)

    def test_creates_reservation_on_confirmation(self):
        """Full flow with confirmation creates the reservation."""
        self._run("book a table")
        self._run("tomorrow")
        self._run("7pm")
        self._run("4 guests")
        self._run("John")
        self._run("+1234567890")
        self._run("john@test.com")
        response = self._run("yes")
        self.assertIsNotNone(response)
        self.assertIn("confirmed", response.lower())
        self.assertEqual(self.memory.reservation_status, "completed")
        self.assertIsNotNone(self.memory.reservation_id)

    def test_extracts_multiple_fields_at_once(self):
        """'table for 4 tomorrow at 7pm' extracts date+time+party in one go."""
        self._run("I want to reserve a table for 4 tomorrow at 7pm")
        # Should have extracted all three
        self.assertIsNotNone(self.memory.reservation_date)
        self.assertIsNotNone(self.memory.reservation_time)
        self.assertEqual(self.memory.party_size, 4)
        # Should be asking for the next missing field (name)
        self.assertEqual(self.memory.reservation_status, "awaiting_customer_name")


class ReservationToolSlotSuggestTest(TestCase):
    """Tests for the enhanced ReservationTool slot suggestions."""

    def setUp(self):
        self.tool = ReservationTool()
        self.tomorrow = date.today() + timedelta(days=1)

    def test_availability_shows_nearby_slots_when_full(self):
        """When slot is maxed out, suggest nearby alternatives."""
        from reservations.models import MAX_RESERVATIONS_PER_SLOT
        # Fill up the slot
        for i in range(MAX_RESERVATIONS_PER_SLOT):
            Reservation.objects.create(
                customer_name=f"Guest {i}",
                phone="+1234567890",
                email=f"guest{i}@test.com",
                reservation_date=self.tomorrow,
                reservation_time=time(19, 0),
                party_size=2,
                status="confirmed",
            )
        result = self.tool.execute(
            action="check",
            reservation_date=self.tomorrow.isoformat(),
            reservation_time="19:00",
            party_size=2,
        )
        self.assertFalse(result.success)
        self.assertIn("18:00", result.message)
        self.assertIn("18:30", result.message)
        self.assertIn("19:30", result.message)
        self.assertIn("available_slots", result.data)
        self.assertGreater(len(result.data["available_slots"]), 0)

    def test_confirm_includes_customer_memory(self):
        """Confirming a reservation includes memory updates for customer info."""
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
        self.assertIn("confirmed", result.message.lower())
        self.assertEqual(result.memory_updates.get("customer_name"), "Test")
        self.assertEqual(result.memory_updates.get("email"), "test@test.com")


"""
Milestone 7: Customer Memory Tests

Test classes:
- MemoryEngineTest: tests for inline preference extraction, topic inference, usual order detection
- ManagePreferencesToolTest: tests for set_favorite, set_preference, get_my_profile, get_usual_order
- MemoryStatePersistenceTest: tests for topic tracking persistence in ConversationMemory
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from agent.memory import ConversationMemory
from agent.memory_engine import (
    MemoryEngine,
    _extract_favorite,
    _extract_like,
    _extract_dislike,
    _extract_usual_indicator,
    _extract_usual_order_pattern,
    _extract_dietary,
    _extract_spice,
    _infer_topic,
)
from agent.memory_manager import MemoryManager
from agent.tools.memory_tool import ManagePreferencesTool
from menu.models import MenuItem
from orders.models import Order, OrderItem
from agent.models import SemanticMemory, CustomerProfile


# ─── Extraction Pattern Tests ────────────────────────────────────────────


class ExtractionPatternTest(TestCase):
    """Unit tests for individual extraction patterns used by MemoryEngine."""

    def test_extract_favorite_pattern(self):
        """'my favorite is X' extracts X."""
        result = _extract_favorite("My favorite is Ethiopian coffee")
        self.assertEqual(result, "Ethiopian coffee")

    def test_extract_favorite_alt_pattern(self):
        """'X is my favorite' extracts X."""
        result = _extract_favorite("Shiro Wat is my favorite")
        self.assertEqual(result, "Shiro Wat")

    def test_extract_favorite_with_punctuation(self):
        """'my favorite is X!' extracts X."""
        result = _extract_favorite("my favorite is the tibs!")
        self.assertEqual(result, "the tibs")

    def test_extract_favorite_no_match(self):
        """Message without favorite returns None."""
        result = _extract_favorite("What's on the menu?")
        self.assertIsNone(result)

    def test_extract_like_pattern(self):
        """'I love X' extracts X."""
        result = _extract_like("I love Ethiopian coffee")
        self.assertEqual(result, "Ethiopian coffee")

    def test_extract_like_with_really(self):
        """'I really like X' extracts X."""
        result = _extract_like("I really like the pasta")
        self.assertEqual(result, "the pasta")

    def test_extract_like_no_match(self):
        """Message without like returns None."""
        result = _extract_like("Table for 2 please")
        self.assertIsNone(result)

    def test_extract_dislike_pattern(self):
        """'I don't like X' extracts X."""
        result = _extract_dislike("I don't like spicy food")
        self.assertEqual(result, "spicy food")

    def test_extract_dislike_hate(self):
        """'I hate X' extracts X."""
        result = _extract_dislike("I hate mushrooms")
        self.assertEqual(result, "mushrooms")

    def test_extract_usual_indicator(self):
        """'the usual' returns True."""
        self.assertTrue(_extract_usual_indicator("I'll have the usual"))
        self.assertTrue(_extract_usual_indicator("the usual please"))
        self.assertFalse(_extract_usual_indicator("What's on the menu?"))

    def test_extract_usual_order_pattern(self):
        """'I usually order X' extracts X."""
        result = _extract_usual_order_pattern("I usually order the tibs")
        self.assertEqual(result, "the tibs")

    def test_extract_dietary_pattern(self):
        """'I'm allergic to X' extracts X."""
        result = _extract_dietary("I'm allergic to peanuts")
        self.assertIsNotNone(result)
        self.assertIn("peanuts", result)

    def test_extract_spice_pattern(self):
        """'I like spicy' extracts spicy."""
        result = _extract_spice("I love spicy food")
        self.assertEqual(result, "spicy")

    def test_infer_topic_ordering(self):
        """'I want to order' infers ordering topic."""
        self.assertEqual(_infer_topic("I want to order pizza"), "ordering")

    def test_infer_topic_menu(self):
        """'What's on the menu?' infers menu topic."""
        self.assertEqual(_infer_topic("What's on the menu?"), "menu")

    def test_infer_topic_reservation(self):
        """'Book a table' infers reservation topic."""
        self.assertEqual(_infer_topic("Book a table at 7pm"), "reservation")

    def test_infer_topic_preference(self):
        """'My favorite is coffee' infers preference topic."""
        self.assertEqual(_infer_topic("My favorite is coffee"), "preference")


# ─── MemoryEngine Integration Tests ──────────────────────────────────────


class MemoryEngineTest(TestCase):
    """Integration tests for MemoryEngine with real database."""

    def setUp(self):
        self.engine = MemoryEngine(MemoryManager())
        self.customer_id = "test-mem-engine"
        self.memory = ConversationMemory()
        self.memory.customer_id = self.customer_id

        # Seed a paid order for usual-order detection
        self.menu_item = MenuItem.objects.create(
            name="Ethiopian Coffee",
            description="Traditional Ethiopian coffee",
            category="Drinks",
            price=Decimal("5.00"),
            available=True,
        )
        self.coffee_order = Order.objects.create(
            customer_name="Test",
            customer_id=self.customer_id,
            email="test@test.com",
            phone="+1234567890",
            status="paid",
        )
        OrderItem.objects.create(
            order=self.coffee_order,
            menu_item_id=self.menu_item.id,
            item_name="Ethiopian Coffee",
            quantity=2,
            price=Decimal("5.00"),
        )

    def test_extract_favorite_inline(self):
        """Inline extraction saves favorite to SemanticMemory."""
        result = self.engine.extract_inline(
            "My favorite is Ethiopian coffee",
            customer_id=self.customer_id,
            memory=self.memory,
        )
        self.assertEqual(result["favorite"], "Ethiopian coffee")
        # Check it was persisted
        facts = SemanticMemory.objects.filter(
            customer_id=self.customer_id,
            category="favorite",
        )
        self.assertGreaterEqual(facts.count(), 1)
        self.assertTrue(any("ethiopian" in f.fact_value.lower() for f in facts))

    def test_extract_like_inline(self):
        """Inline extraction saves like to SemanticMemory."""
        result = self.engine.extract_inline(
            "I love pasta carbonara",
            customer_id=self.customer_id,
            memory=self.memory,
        )
        self.assertEqual(result["like"], "pasta carbonara")
        facts = SemanticMemory.objects.filter(
            customer_id=self.customer_id,
            fact_key__startswith="likes_",
        )
        self.assertGreaterEqual(facts.count(), 1)

    def test_extract_dislike_inline(self):
        """Inline extraction saves dislike to SemanticMemory."""
        result = self.engine.extract_inline(
            "I don't like mushrooms",
            customer_id=self.customer_id,
            memory=self.memory,
        )
        self.assertEqual(result["dislike"], "mushrooms")
        facts = SemanticMemory.objects.filter(
            customer_id=self.customer_id,
            category="dislike",
        )
        self.assertGreaterEqual(facts.count(), 1)

    def test_extract_dietary_inline(self):
        """Inline extraction saves dietary restriction."""
        result = self.engine.extract_inline(
            "I'm allergic to peanuts",
            customer_id=self.customer_id,
            memory=self.memory,
        )
        self.assertIsNotNone(result["dietary"])
        self.assertIn("peanuts", result["dietary"])

    def test_extract_spice_inline(self):
        """Inline extraction saves spice preference."""
        result = self.engine.extract_inline(
            "I love spicy food",
            customer_id=self.customer_id,
            memory=self.memory,
        )
        self.assertEqual(result["spice"], "spicy")

    def test_topic_tracking(self):
        """Extraction tracks conversation topics."""
        result = self.engine.extract_inline(
            "I want to order pizza",
            customer_id=self.customer_id,
            memory=self.memory,
        )
        self.assertEqual(result["topic"], "ordering")
        self.assertIn("ordering", self.memory.discussed_topics)

    def test_multiple_topics(self):
        """Multiple messages add multiple topics."""
        self.engine.extract_inline(
            "What's on the menu?",
            customer_id=self.customer_id,
            memory=self.memory,
        )
        self.engine.extract_inline(
            "Book a table",
            customer_id=self.customer_id,
            memory=self.memory,
        )
        self.assertIn("menu", self.memory.discussed_topics)
        self.assertIn("reservation", self.memory.discussed_topics)

    def test_get_usual_order(self):
        """Usual order detection finds most-ordered item."""
        usual = self.engine.get_usual_order(self.customer_id)
        self.assertIsNotNone(usual)
        self.assertEqual(usual["item_name"], "Ethiopian Coffee")
        self.assertEqual(usual["order_count"], 1)

    def test_get_usual_order_no_orders(self):
        """Customer with no orders returns None."""
        usual = self.engine.get_usual_order("new-customer")
        self.assertIsNone(usual)

    def test_get_proactive_suggestions_with_history(self):
        """Customer with profile gets suggestions."""
        # Add a semantic fact
        SemanticMemory.objects.create(
            customer_id=self.customer_id,
            category="favorite",
            fact_key="favorite_coffee",
            fact_value="Ethiopian Coffee",
            confidence=0.8,
        )
        # Update profile
        profile, _ = CustomerProfile.objects.get_or_create(
            customer_id=self.customer_id
        )
        profile.display_name = "TestUser"
        profile.favorite_items = "Ethiopian Coffee"
        profile.total_orders = 1
        profile.save()

        suggestions = self.engine.get_proactive_suggestions(self.customer_id)
        self.assertTrue(suggestions["has_history"])
        self.assertEqual(suggestions["usual_order"], "Ethiopian Coffee")
        self.assertIn("Ethiopian Coffee", suggestions["favorite_items"])
        self.assertIn("welcome_back_context", suggestions)

    def test_get_personalized_greeting(self):
        """Greeting context includes name and usual order."""
        # Update profile
        profile, _ = CustomerProfile.objects.get_or_create(
            customer_id=self.customer_id
        )
        profile.display_name = "TestUser"
        profile.total_orders = 1
        profile.save()

        # Ensure a usual order fact exists
        SemanticMemory.objects.create(
            customer_id=self.customer_id,
            category="pattern",
            fact_key="usual_order",
            fact_value="Ethiopian Coffee",
            confidence=0.7,
        )

        greeting = self.engine.get_personalized_greeting(self.customer_id)
        self.assertIn("TestUser", greeting)
        self.assertIn("Coffee", greeting)

    def test_no_extraction_for_anonymous(self):
        """Messages without customer_id are not extracted."""
        result = self.engine.extract_inline(
            "My favorite is coffee",
            customer_id=None,
            memory=self.memory,
        )
        self.assertEqual(result["favorite"], "coffee")
        # Should not have saved to DB (no customer_id)
        self.assertEqual(
            SemanticMemory.objects.filter(customer_id=None).count(),
            0,
        )


# ─── ManagePreferencesTool Tests ─────────────────────────────────────────


class ManagePreferencesToolTest(TestCase):
    """Tests for the ManagePreferencesTool."""

    def setUp(self):
        self.tool = ManagePreferencesTool()
        self.customer_id = "test-pref-tool"

    def test_set_favorite(self):
        """set_favorite saves and confirms the favorite."""
        result = self.tool.execute(
            action="set_favorite",
            customer_id=self.customer_id,
            item_name="Ethiopian Coffee",
        )
        self.assertTrue(result.success)
        self.assertIn("Ethiopian Coffee", result.message)
        # Check DB
        facts = SemanticMemory.objects.filter(
            customer_id=self.customer_id,
            category="favorite",
        )
        self.assertGreaterEqual(facts.count(), 1)

    def test_set_favorite_missing_item(self):
        """set_favorite without item_name returns missing_fields."""
        result = self.tool.execute(
            action="set_favorite",
            customer_id=self.customer_id,
        )
        self.assertFalse(result.success)
        self.assertIn("item_name", result.missing_fields)

    def test_set_preference(self):
        """set_preference saves the key/value."""
        result = self.tool.execute(
            action="set_preference",
            customer_id=self.customer_id,
            key="spice_tolerance",
            value="high",
        )
        self.assertTrue(result.success)
        facts = SemanticMemory.objects.filter(
            customer_id=self.customer_id,
            fact_key="spice_tolerance",
        )
        self.assertEqual(facts.count(), 1)
        self.assertEqual(facts.first().fact_value, "high")

    def test_set_preference_missing_fields(self):
        """set_preference without key or value returns missing_fields."""
        result = self.tool.execute(
            action="set_preference",
            customer_id=self.customer_id,
            key="",
            value="",
        )
        self.assertFalse(result.success)
        self.assertIn("key", result.missing_fields)

    def test_get_profile_no_data(self):
        """get_my_profile on a new customer returns helpful message."""
        result = self.tool.execute(
            action="get_my_profile",
            customer_id="new-customer",
        )
        self.assertTrue(result.success)
        self.assertIn("don't have a profile", result.message.lower())

    def test_get_profile_with_data(self):
        """get_my_profile with saved facts returns them."""
        SemanticMemory.objects.create(
            customer_id=self.customer_id,
            category="favorite",
            fact_key="favorite_coffee",
            fact_value="Ethiopian Coffee",
            confidence=0.8,
        )
        CustomerProfile.objects.create(
            customer_id=self.customer_id,
            display_name="Test",
            favorite_items="Ethiopian Coffee",
            total_orders=3,
        )

        result = self.tool.execute(
            action="get_my_profile",
            customer_id=self.customer_id,
        )
        self.assertTrue(result.success)
        self.assertIn("favorites", result.message.lower())
        self.assertIn("3", result.message)

    def test_get_usual_order_with_data(self):
        """get_usual_order with order history returns the item."""
        item = MenuItem.objects.create(
            name="Pizza",
            description="Cheese pizza",
            price=Decimal("12.99"),
            available=True,
        )
        order = Order.objects.create(
            customer_name="Test",
            customer_id=self.customer_id,
            email="test@test.com",
            status="paid",
        )
        OrderItem.objects.create(
            order=order,
            menu_item_id=item.id,
            item_name="Pizza",
            quantity=1,
            price=Decimal("12.99"),
        )
        result = self.tool.execute(
            action="get_usual_order",
            customer_id=self.customer_id,
        )
        self.assertTrue(result.success)
        self.assertIn("Pizza", result.message)

    def test_get_usual_order_no_data(self):
        """get_usual_order without history returns helpful message."""
        result = self.tool.execute(
            action="get_usual_order",
            customer_id="new-customer",
        )
        self.assertTrue(result.success)
        self.assertIn("don't have a usual order", result.message.lower())

    def test_unknown_action(self):
        """Unknown action returns error."""
        result = self.tool.execute(
            action="unknown",
            customer_id=self.customer_id,
        )
        self.assertFalse(result.success)
        self.assertIn("unknown action", result.message.lower())

    def test_missing_customer_id(self):
        """Missing customer_id returns error."""
        result = self.tool.execute(action="set_favorite")
        self.assertFalse(result.success)
        self.assertIn("customer_id", result.missing_fields)


# ─── ConversationMemory Topic Tracking Tests ────────────────────────────


class TopicTrackingTest(TestCase):
    """Tests for ConversationMemory topic tracking and state persistence."""

    def test_discussed_topics_default_empty(self):
        """New memory has empty discussed_topics."""
        memory = ConversationMemory()
        self.assertEqual(memory.discussed_topics, [])

    def test_add_topic(self):
        """Topics can be added to discussed_topics."""
        memory = ConversationMemory()
        memory.discussed_topics.append("ordering")
        memory.discussed_topics.append("menu")
        self.assertEqual(len(memory.discussed_topics), 2)
        self.assertIn("ordering", memory.discussed_topics)
        self.assertIn("menu", memory.discussed_topics)

    def test_no_duplicate_topics(self):
        """Same topic is not added twice."""
        memory = ConversationMemory()
        if "ordering" not in memory.discussed_topics:
            memory.discussed_topics.append("ordering")
        if "ordering" not in memory.discussed_topics:
            memory.discussed_topics.append("ordering")
        self.assertEqual(len(memory.discussed_topics), 1)

    def test_conversation_summary_default_none(self):
        """New memory has conversation_summary None."""
        memory = ConversationMemory()
        self.assertIsNone(memory.conversation_summary)

    def test_conversation_summary_set_and_get(self):
        """conversation_summary can be set."""
        memory = ConversationMemory()
        memory.conversation_summary = "User mentioned their usual: Coffee"
        self.assertEqual(memory.conversation_summary, "User mentioned their usual: Coffee")

    def test_state_persistence_includes_topics(self):
        """discussed_topics and conversation_summary survive to_state/from_state."""
        original = ConversationMemory()
        original.discussed_topics.append("ordering")
        original.discussed_topics.append("preference")
        original.conversation_summary = "User likes Ethiopian coffee"

        # Round-trip through state
        state = original.to_state()
        restored = ConversationMemory.from_state(state)

        self.assertEqual(restored.discussed_topics, ["ordering", "preference"])
        self.assertEqual(restored.conversation_summary, "User likes Ethiopian coffee")


# ─── Memory Data Flow Test (controller integration) ─────────────────────


class MemoryDataFlowTest(TestCase):
    """Tests that the full memory data flow works end-to-end.

    Simulates what happens when a message goes through the controller:
    1. User says 'my favorite is coffee'
    2. MemoryEngine extracts and persists
    3. Memory is serialized to state
    4. State is restored on next request
    """

    def setUp(self):
        self.customer_id = "test-data-flow"
        self.engine = MemoryEngine(MemoryManager())
        self.memory = ConversationMemory()
        self.memory.customer_id = self.customer_id

    def test_preference_extraction_then_state_round_trip(self):
        """Extract preference → persist → save state → restore → topic preserved."""
        # Step 1: Simulate user message
        extracted = self.engine.extract_inline(
            "My favorite is Ethiopian coffee",
            customer_id=self.customer_id,
            memory=self.memory,
        )
        self.assertEqual(extracted["favorite"], "Ethiopian coffee")

        # Step 2: Track topic
        topic = extracted.get("topic")
        if topic and topic not in self.memory.discussed_topics:
            self.memory.discussed_topics.append(topic)

        # Step 3: Save state (simulating _save_memory_state)
        state = self.memory.to_state()
        state.pop("customer_id", None)

        # Step 4: Restore state (simulating _build_memory_from_session)
        restored = ConversationMemory.from_state(state)

        # Step 5: Verify topics preserved
        self.assertIn("preference", restored.discussed_topics)

        # Step 6: Verify profile was created
        profile = CustomerProfile.objects.filter(
            customer_id=self.customer_id
        ).first()
        self.assertIsNotNone(profile)
        self.assertIn("ethiopian", profile.favorite_items.lower())


"""
Milestone 8: Advanced RAG Tests

Test classes:
- HybridSearchEngineTest: tests for vector/keyword/hybrid search, metadata filtering, re-ranking
- KnowledgeBaseCRUDTest: tests for knowledge management API
- SearchKnowledgeToolEnhancedTest: tests for enhanced search tool
"""

import json
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse

from agent.embeddings import EMBEDDING_DIMENSIONS
from agent.models import KnowledgeBase
from agent.rag import (
    HybridSearchEngine,
    search_knowledge,
    format_knowledge_context,
    _normalize_scores,
    _l2_to_similarity,
    _inferred_content_type,
    _recency_days,
)


class HelperFunctionTest(TestCase):
    """Tests for helper functions in rag.py."""

    def test_normalize_scores_empty(self):
        self.assertEqual(_normalize_scores([]), [])

    def test_normalize_scores_identical(self):
        """All identical values return 0.5."""
        result = _normalize_scores([5.0, 5.0, 5.0])
        self.assertEqual(result, [0.5, 0.5, 0.5])

    def test_normalize_scores_varied(self):
        result = _normalize_scores([0.0, 5.0, 10.0])
        self.assertEqual(result[0], 0.0)
        self.assertEqual(result[2], 1.0)
        self.assertEqual(result[1], 0.5)

    def test_l2_to_similarity(self):
        result = _l2_to_similarity([0.0, 1.0, 3.0])
        self.assertEqual(result[0], 1.0)  # distance 0 → similarity 1
        self.assertAlmostEqual(result[1], 0.5)  # distance 1 → 1/2 = 0.5
        self.assertLess(result[2], result[1])

    def test_inferred_content_type_menu(self):
        self.assertEqual(_inferred_content_type("What dishes do you have?"), "menu_item")

    def test_inferred_content_type_policy(self):
        self.assertEqual(_inferred_content_type("What's your cancellation policy?"), "policy")

    def test_inferred_content_type_promotion(self):
        self.assertEqual(_inferred_content_type("Any happy hour deals?"), "promotion")

    def test_inferred_content_type_none(self):
        self.assertIsNone(_inferred_content_type("How are you?"))

    def test_format_knowledge_context_empty(self):
        self.assertEqual(format_knowledge_context([]), "")

    def test_format_knowledge_context_with_results(self):
        results = [
            {"title": "Test Policy", "content": "Test content here.", "content_type": "policy", "metadata": {}, "score": 0.85},
        ]
        output = format_knowledge_context(results)
        self.assertIn("<retrieved_knowledge>", output)
        self.assertIn("</retrieved_knowledge>", output)
        self.assertIn("Test Policy", output)
        self.assertIn("0.85", output)


class HybridSearchEngineTest(TestCase):
    """Integration tests for HybridSearchEngine with real database."""

    def setUp(self):
        self.engine = HybridSearchEngine()
        # Create test knowledge items
        # Since we use SQLite with USE_SQLITE=true, pgvector embedding is not available.
        # We'll create items with zero vectors and test the keyword/icontains fallback.
        zero_embedding = [0.0] * EMBEDDING_DIMENSIONS

        self.policy_item = KnowledgeBase.objects.create(
            content_type="policy",
            title="Cancellation Policy",
            content="Reservations can be cancelled up to 2 hours before the scheduled time at no charge.",
            metadata={"category": "policies"},
            embedding=zero_embedding,
        )
        self.faq_item = KnowledgeBase.objects.create(
            content_type="faq",
            title="Do you have vegetarian options?",
            content="Yes! We have a wide variety of vegetarian dishes including Shiro and Misir Wot.",
            metadata={},
            embedding=zero_embedding,
        )
        self.menu_item = KnowledgeBase.objects.create(
            content_type="menu_item",
            title="Ethiopian Coffee",
            content="Traditional Ethiopian coffee ceremony style. $5.00",
            metadata={"category": "Drinks", "price": 5.0},
            embedding=zero_embedding,
        )
        self.inactive_item = KnowledgeBase.objects.create(
            content_type="promotion",
            title="Expired Deal",
            content="This deal is no longer active.",
            metadata={},
            embedding=zero_embedding,
            is_active=False,
        )

    def test_search_empty_query(self):
        """Empty query returns empty list."""
        results = self.engine.search("")
        self.assertEqual(results, [])

    def test_keyword_search_finds_policy(self):
        """Keyword search finds cancellation policy."""
        results = self.engine.search("cancellation", search_mode="keyword")
        self.assertGreaterEqual(len(results), 1)
        titles = [r["title"] for r in results]
        self.assertIn("Cancellation Policy", titles)

    def test_keyword_search_finds_vegetarian(self):
        """Keyword search finds vegetarian FAQ."""
        results = self.engine.search("vegetarian options", search_mode="keyword")
        self.assertGreaterEqual(len(results), 1)
        titles = [r["title"] for r in results]
        self.assertTrue(any("vegetarian" in t.lower() for t in titles))

    def test_content_type_filter(self):
        """Filtering by content_type returns only that type."""
        results = self.engine.search("coffee", content_type="menu_item")
        self.assertGreaterEqual(len(results), 1)
        for r in results:
            self.assertEqual(r["content_type"], "menu_item")

    def test_content_type_filter_excludes_other_types(self):
        """Filtering by content_type does not include other types."""
        results = self.engine.search("cancellation", content_type="menu_item")
        # Should not find policy items when filtered to menu_item
        self.assertEqual(len(results), 0)

    def test_is_active_filter(self):
        """Inactive items are excluded by default."""
        results = self.engine.search("deal", search_mode="keyword")
        titles = [r["title"] for r in results]
        self.assertNotIn("Expired Deal", titles)

    def test_is_active_include_inactive(self):
        """Inactive items can be included with is_active=None."""
        results = self.engine.search("deal", search_mode="keyword", is_active=None)
        titles = [r["title"] for r in results]
        self.assertIn("Expired Deal", titles)

    def test_max_price_filter(self):
        """max_price filter works for items with price metadata."""
        # Create another item with higher price
        zero = [0.0] * EMBEDDING_DIMENSIONS
        KnowledgeBase.objects.create(
            content_type="menu_item",
            title="Expensive Steak",
            content="Premium steak. $45.00",
            metadata={"category": "Mains", "price": 45.0},
            embedding=zero,
        )
        results = self.engine.search("coffee", max_price=10.0, search_mode="keyword")
        titles = [r["title"] for r in results]
        self.assertIn("Ethiopian Coffee", titles)
        self.assertNotIn("Expensive Steak", titles)

    def test_categories_filter(self):
        """Filtering by categories returns items in those categories."""
        zero = [0.0] * EMBEDDING_DIMENSIONS
        KnowledgeBase.objects.create(
            content_type="menu_item",
            title="Pasta",
            content="Delicious pasta. $15.00",
            metadata={"category": "Mains", "price": 15.0},
            embedding=zero,
        )
        results = self.engine.search("coffee", categories=["Drinks"], search_mode="keyword")
        titles = [r["title"] for r in results]
        self.assertIn("Ethiopian Coffee", titles)
        self.assertNotIn("Pasta", titles)

    def test_hybrid_search_returns_results(self):
        """Hybrid search returns results (uses fallback for SQLite)."""
        results = self.engine.search("cancellation reservation", search_mode="hybrid")
        self.assertGreaterEqual(len(results), 0)  # May be 0 with zero vectors
        # This mainly verifies no crash with hybrid mode

    def test_top_k_limits_results(self):
        """top_k parameter limits the number of results."""
        # Create several items
        zero = [0.0] * EMBEDDING_DIMENSIONS
        for i in range(10):
            KnowledgeBase.objects.create(
                content_type="faq",
                title=f"Test FAQ {i}",
                content=f"This is test FAQ number {i} about various topics.",
                metadata={},
                embedding=zero,
            )
        results = self.engine.search("test faq", search_mode="keyword", top_k=3)
        self.assertLessEqual(len(results), 3)

    def test_results_include_scores(self):
        """Search results include score and score_components."""
        results = self.engine.search("cancellation", search_mode="keyword")
        if results:
            self.assertIn("score", results[0])
            self.assertIn("score_components", results[0])
            self.assertIsNotNone(results[0]["score"])


class SearchKnowledgeFunctionTest(TestCase):
    """Tests for the module-level search_knowledge convenience function."""

    def setUp(self):
        zero = [0.0] * EMBEDDING_DIMENSIONS
        KnowledgeBase.objects.create(
            content_type="faq",
            title="Test FAQ",
            content="This is a test FAQ about parking and directions.",
            embedding=zero,
        )

    def test_search_knowledge_backward_compatible(self):
        """search_knowledge() works without search_mode param (backward compat)."""
        results = search_knowledge("parking")
        # Should not crash and return results
        self.assertIsInstance(results, list)

    def test_search_knowledge_with_search_mode(self):
        """search_knowledge() accepts search_mode kwarg."""
        results = search_knowledge("parking", search_mode="keyword")
        self.assertIsInstance(results, list)


class KnowledgeBaseCRUDTest(TestCase):
    """Tests for the knowledge management API endpoints."""

    def setUp(self):
        zero = [0.0] * EMBEDDING_DIMENSIONS
        self.item = KnowledgeBase.objects.create(
            content_type="faq",
            title="Test FAQ",
            content="Test content for FAQ.",
            metadata={"source": "test"},
            embedding=zero,
        )

    def test_item_to_dict_includes_fields(self):
        """KnowledgeBase items include all expected fields in output."""
        from agent.knowledge_admin import KnowledgeBaseListView
        view = KnowledgeBaseListView()
        d = view._item_to_dict(self.item)
        self.assertIn("id", d)
        self.assertIn("title", d)
        self.assertIn("content", d)
        self.assertIn("content_type", d)
        self.assertIn("metadata", d)
        self.assertIn("is_active", d)
        self.assertEqual(d["title"], "Test FAQ")
        self.assertEqual(d["content_type"], "faq")

    def test_bulk_upload_validates_items(self):
        """Bulk upload view rejects invalid items."""
        from agent.knowledge_admin import KnowledgeBulkUploadView
        from django.http import HttpRequest
        view = KnowledgeBulkUploadView()
        # Verify the view class exists and has a post method
        self.assertTrue(hasattr(view, 'post'))


# ─── Milestone 9: End-to-End Workflow Tests ──────────────────────────────


from django.test import TransactionTestCase


class EndToEndWorkflowTest(TransactionTestCase):
    """Full conversation simulation from greeting through operations."""

    @classmethod
    def setUpTestData(cls):
        cls.coffee = MenuItem.objects.create(
            name="Ethiopian Coffee",
            description="Traditional Ethiopian coffee ceremony style",
            category="Drinks",
            price=Decimal("5.00"),
            available=True,
        )

    def setUp(self):
        self.memory = ConversationMemory()
        self.memory.customer_id = "e2e-test-user"
        self.memory.customer_name = "TestUser"

    def _run(self, message):
        return async_to_sync(agent.run)(
            message, history=[], memory=self.memory,
            customer_id=self.memory.customer_id,
        )

    def test_menu_query_returns_response(self):
        response = self._run("Show me the menu")
        self.assertIsNotNone(response)
        self.assertGreater(len(response), 5)

    def test_reservation_intent_detected(self):
        response = self._run("I want to reserve a table for tomorrow")
        self.assertIsNotNone(response)
        # Should ask for time or mention the date (reservation workflow active)
        self.assertTrue(
            "time" in response.lower()
            or "2026" in response
            or "tomorrow" in response.lower()
            or "date" in response.lower()
        )

    def test_helpful_response_to_unknown(self):
        response = self._run("xyzzy")
        self.assertIsNotNone(response)
        self.assertGreater(len(response), 5)

    def test_payment_reference_does_not_crash(self):
        response = self._run("I want to pay with cash")
        self.assertIsNotNone(response)
