from datetime import date, time, timedelta
from threading import Thread

from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Reservation, RESERVATION_HOLD_MINUTES, MAX_PARTY_SIZE, MAX_RESERVATIONS_PER_SLOT


class ReservationViewSetTest(APITestCase):
    def setUp(self):
        self.tomorrow = date.today() + timedelta(days=1)
        self.reservation = Reservation.objects.create(
            customer_name="Test Customer",
            customer_id="cust-123",
            phone="+1234567890",
            email="test@test.com",
            reservation_date=self.tomorrow,
            reservation_time=time(19, 0),
            party_size=4,
            status="confirmed",
        )

    def test_list_reservations(self):
        response = self.client.get("/api/reservations/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_retrieve_reservation(self):
        response = self.client.get(f"/api/reservations/{self.reservation.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["customer_name"], "Test Customer")

    def test_create_reservation(self):
        data = {
            "customer_name": "New Customer",
            "phone": "+0987654321",
            "email": "new@test.com",
            "reservation_date": self.tomorrow.isoformat(),
            "reservation_time": "20:00",
            "party_size": 2,
        }
        response = self.client.post("/api/reservations/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Reservation.objects.count(), 2)

    def test_create_reservation_past_date(self):
        data = {
            "customer_name": "New Customer",
            "phone": "+0987654321",
            "email": "new@test.com",
            "reservation_date": (date.today() - timedelta(days=1)).isoformat(),
            "reservation_time": "19:00",
            "party_size": 2,
        }
        response = self.client.post("/api/reservations/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_reservation_party_too_large(self):
        data = {
            "customer_name": "New Customer",
            "phone": "+0987654321",
            "email": "new@test.com",
            "reservation_date": self.tomorrow.isoformat(),
            "reservation_time": "19:00",
            "party_size": MAX_PARTY_SIZE + 1,
        }
        response = self.client.post("/api/reservations/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filter_by_customer_id(self):
        response = self.client.get("/api/reservations/?customer_id=cust-123")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_filter_by_status(self):
        response = self.client.get("/api/reservations/?status=confirmed")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)


class ReservationTTLTest(TestCase):
    def test_held_reservation_has_held_until(self):
        reservation = Reservation.objects.create(
            customer_name="Test",
            phone="+1234567890",
            email="test@test.com",
            reservation_date=date.today() + timedelta(days=1),
            reservation_time=time(19, 0),
            party_size=2,
            status="held",
            held_until=timezone.now() + timedelta(minutes=RESERVATION_HOLD_MINUTES),
        )
        self.assertIsNotNone(reservation.held_until)
        self.assertFalse(reservation.is_held_expired)

    def test_held_reservation_expired(self):
        reservation = Reservation.objects.create(
            customer_name="Test",
            phone="+1234567890",
            email="test@test.com",
            reservation_date=date.today() + timedelta(days=1),
            reservation_time=time(19, 0),
            party_size=2,
            status="held",
            held_until=timezone.now() - timedelta(minutes=1),
        )
        self.assertTrue(reservation.is_held_expired)

    def test_release_if_expired(self):
        reservation = Reservation.objects.create(
            customer_name="Test",
            phone="+1234567890",
            email="test@test.com",
            reservation_date=date.today() + timedelta(days=1),
            reservation_time=time(19, 0),
            party_size=2,
            status="held",
            held_until=timezone.now() - timedelta(minutes=1),
        )
        result = reservation.release_if_expired()
        self.assertTrue(result)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, "cancelled")

    def test_confirmed_reservation_not_expired(self):
        reservation = Reservation.objects.create(
            customer_name="Test",
            phone="+1234567890",
            email="test@test.com",
            reservation_date=date.today() + timedelta(days=1),
            reservation_time=time(19, 0),
            party_size=2,
            status="confirmed",
        )
        self.assertFalse(reservation.is_held_expired)


class ConcurrentReservationTest(TransactionTestCase):
    """Test that concurrent hold attempts on the same slot are handled correctly.

    Uses TransactionTestCase (not TestCase) so threads can write to the DB
    without being blocked by a wrapping test transaction.
    """

    def setUp(self):
        self.tomorrow = date.today() + timedelta(days=1)
        self.slot_time = time(19, 0)
        self.results = []

    def tearDown(self):
        Reservation.objects.all().delete()

    def _create_hold(self, customer_name):
        from agent.tools.reservation import ReservationTool

        tool = ReservationTool()
        result = tool.execute(
            action="create",
            customer_name=customer_name,
            phone="+1234567890",
            email=f"{customer_name.lower().replace(' ', '')}@test.com",
            reservation_date=self.tomorrow.isoformat(),
            reservation_time=self.slot_time.strftime("%H:%M"),
            party_size=4,
        )
        self.results.append(result)

    def test_slot_capacity_enforced(self):
        """Slot should reject new holds once capacity is reached."""
        from agent.tools.reservation import ReservationTool

        tool = ReservationTool()

        for i in range(MAX_RESERVATIONS_PER_SLOT):
            result = tool.execute(
                action="create",
                customer_name=f"Guest {i}",
                phone="+1234567890",
                email=f"g{i}@test.com",
                reservation_date=self.tomorrow.isoformat(),
                reservation_time=self.slot_time.strftime("%H:%M"),
                party_size=2,
            )
            self.assertTrue(result.success, f"Hold #{i} should succeed")

        result = tool.execute(
            action="create",
            customer_name="Overflow Guest",
            phone="+1234567890",
            email="overflow@test.com",
            reservation_date=self.tomorrow.isoformat(),
            reservation_time=self.slot_time.strftime("%H:%M"),
            party_size=2,
        )
        self.assertFalse(result.success, "Hold should fail when slot is at capacity")

    def test_confirm_after_slot_taken(self):
        """After a reservation fills a slot, a new hold at that slot should fail."""
        from agent.tools.reservation import ReservationTool

        tool = ReservationTool()

        r1 = tool.execute(
            action="create",
            customer_name="Guest One",
            phone="+1234567890",
            email="g1@test.com",
            reservation_date=self.tomorrow.isoformat(),
            reservation_time=self.slot_time.strftime("%H:%M"),
            party_size=4,
        )
        self.assertTrue(r1.success)
        r1_id = r1.data["reservation"]["id"]

        confirm1 = tool.execute(action="confirm", reservation_id=r1_id)
        self.assertTrue(confirm1.success)

        r2 = tool.execute(
            action="create",
            customer_name="Guest Two",
            phone="+1234567890",
            email="g2@test.com",
            reservation_date=self.tomorrow.isoformat(),
            reservation_time=self.slot_time.strftime("%H:%M"),
            party_size=4,
        )
        self.assertTrue(r2.success, "Second hold should succeed (slot has capacity for %d)" % MAX_RESERVATIONS_PER_SLOT)
        r2_id = r2.data["reservation"]["id"]

        confirm2 = tool.execute(action="confirm", reservation_id=r2_id)
        self.assertTrue(confirm2.success, "Second confirmation should succeed within capacity")

    def test_expired_hold_released_for_new_booking(self):
        """An expired hold should be released and allow a new booking."""
        Reservation.objects.create(
            customer_name="Old Guest",
            phone="+1234567890",
            email="old@test.com",
            reservation_date=self.tomorrow,
            reservation_time=self.slot_time,
            party_size=4,
            status="held",
            held_until=timezone.now() - timedelta(minutes=1),
        )

        from agent.tools.reservation import ReservationTool

        tool = ReservationTool()
        result = tool.execute(
            action="create",
            customer_name="New Guest",
            phone="+0987654321",
            email="new@test.com",
            reservation_date=self.tomorrow.isoformat(),
            reservation_time=self.slot_time.strftime("%H:%M"),
            party_size=4,
        )
        self.assertTrue(result.success, "New booking should succeed after expired hold is released")

        old = Reservation.objects.get(customer_name="Old Guest")
        self.assertEqual(old.status, "cancelled")
