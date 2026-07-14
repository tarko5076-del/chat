from datetime import date, time, timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Reservation, RESERVATION_HOLD_MINUTES, MAX_PARTY_SIZE


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
        self.assertEqual(len(response.data["results"]), 1)

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
        self.assertEqual(len(response.data["results"]), 1)

    def test_filter_by_status(self):
        response = self.client.get("/api/reservations/?status=confirmed")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)


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
