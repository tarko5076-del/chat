"""
Locust load testing script for the Restaurant AI Agent chat endpoint.

Usage:
    # Install Locust
    pip install locust

    # Run with web UI
    locust -f locustfile.py --host=http://localhost:8000

    # Run headless (10 users, 5 spawned per second, 2 minute run)
    locust -f locustfile.py --host=http://localhost:8000 \\
        --headless --users 10 --spawn-rate 5 --run-time 2m

    # Run through the frontend proxy (port 80)
    locust -f locustfile.py --host=http://localhost

    # Custom test users
    locust -f locustfile.py --host=http://localhost \\
        -u 20 -r 5 --run-time 5m \\
        --csv=results/load_test

Setup:
    The script auto-registers test users on first run using a random email
    prefix. Make sure the backend is running with user registration enabled.
"""

import json
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from locust import HttpUser, between, events, task
from locust.exception import RescheduleTask

# ── Configuration ───────────────────────────────────────────────────────

# Messages that simulate real guest interactions
MENU_QUERIES = [
    "What's on the menu today?",
    "Do you have any vegan options?",
    "What appetizers do you serve?",
    "I'm looking for something spicy",
    "What desserts are available?",
    "Do you have gluten-free dishes?",
    "What's your most popular dish?",
    "Can you recommend something light?",
    "What drinks do you have?",
    "Show me the breakfast menu",
]

ORDER_QUERIES = [
    "I'd like to order a pizza",
    "Can I get two burgers and fries?",
    "I want to place an order for delivery",
    "Add a salad to my order",
    "What's in my current order?",
    "I'd like to cancel my order",
    "Can I see my order history?",
    "I want to reorder my last meal",
]

RESERVATION_QUERIES = [
    "I want to book a table for tonight",
    "Can I reserve for 4 people tomorrow?",
    "Check if you have a table at 7pm",
    "I need to cancel my reservation",
]

GENERAL_QUERIES = [
    "What are your opening hours?",
    "Do you have a dress code?",
    "What's your cancellation policy?",
    "Hi, how are you today?",
    "Thanks for the help!",
    "Can I speak to a manager?",
    "What payment methods do you accept?",
    "Is there parking available?",
]


@dataclass
class TestSession:
    """Tracks a user's conversation session across tasks."""
    session_id: str | None = None
    customer_id: str | None = None
    customer_name: str | None = None
    email: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    messages_sent: int = 0
    consecutive_failures: int = 0


def _random_name() -> str:
    adjectives = ["happy", "swift", "calm", "bold", "keen", "warm", "bright", "quick"]
    nouns = ["guest", "diner", "patron", "taster", "feaster", "foodie"]
    return f"{random.choice(adjectives)}_{random.choice(nouns)}_{uuid.uuid4().hex[:6]}"


def _random_email(name: str) -> str:
    return f"{name}@loadtest.example.com"


def _pick_message(pool: list[str]) -> str:
    return random.choice(pool)


# ── Events ──────────────────────────────────────────────────────────────


@events.init.add_listener
def on_locust_init(environment, **_kwargs):
    """Log at startup to confirm the script loaded."""
    logging.info("Locust load test initialised — chat endpoint: %s", environment.host or "http://localhost:8000")
    logging.info("Rate limit awareness: chat endpoint throttles at 15 req/min/user")
    logging.info("Each virtual user will wait 4–10s between requests to stay under the limit")


# ── Load Test User ──────────────────────────────────────────────────────


class ChatUser(HttpUser):
    """
    Simulates a restaurant guest interacting with the AI agent via chat.

    Each virtual user:
    1. Registers a new account (or reuses an existing one)
    2. Logs in to get a JWT token
    3. Sends a mix of menu, order, reservation, and general queries
    4. Waits 4–10 seconds between requests (simulating think time)
    """

    # Wait between tasks — short enough to generate load but respects 15/min throttle
    wait_time = between(4.0, 10.0)

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.session = TestSession()
        self._setup_session()

    def _setup_session(self) -> None:
        """Prepare user credentials — register and log in."""
        name = _random_name()
        self.session.customer_name = name
        self.session.email = _random_email(name)

    def on_start(self) -> None:
        """Register and log in when the virtual user starts."""
        self._register()
        self._login()

    # ── Auth: Registration ───────────────────────────────────────────

    def _register(self) -> None:
        """Register a new test user. Fails fast if registration is broken."""
        payload = {
            "username": self.session.customer_name,
            "email": self.session.email,
            "password": "testpass123!",
        }

        # Try the registration endpoint
        with self.client.post(
            "/api/users/register/",
            json=payload,
            catch_response=True,
            name="01_register",
        ) as resp:
            if resp.status_code == 201:
                resp.success()
                logging.debug("Registered user: %s", self.session.email)
            elif resp.status_code == 400:
                # User likely already exists — that's fine
                resp.success()
            else:
                resp.failure(f"Registration failed: {resp.status_code} {resp.text[:200]}")
                raise RescheduleTask()

    # ── Auth: Login ──────────────────────────────────────────────────

    def _login(self) -> None:
        """Log in as the test user and store tokens."""
        payload = {
            "email": self.session.email,
            "password": "testpass123!",
        }

        with self.client.post(
            "/api/users/login/",
            json=payload,
            catch_response=True,
            name="02_login",
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                self.session.access_token = data.get("access") or data.get("token", "")
                self.session.refresh_token = data.get("refresh", "")
                resp.success()
                logging.debug("Logged in as: %s", self.session.email)
            else:
                resp.failure(f"Login failed: {resp.status_code} {resp.text[:200]}")
                raise RescheduleTask()

    # ── Auth: Token Refresh ──────────────────────────────────────────

    def _refresh_token(self) -> bool:
        """Attempt to refresh the access token. Returns True on success."""
        if not self.session.refresh_token:
            return False

        with self.client.post(
            "/api/users/token/refresh/",
            json={"refresh": self.session.refresh_token},
            catch_response=True,
            name="03_token_refresh",
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                new_token = data.get("access", "")
                if new_token:
                    self.session.access_token = new_token
                    resp.success()
                    return True
            resp.failure(f"Token refresh failed: {resp.status_code}")
            return False

    # ── Common request headers ───────────────────────────────────────

    def _auth_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.session.access_token:
            headers["Authorization"] = f"Bearer {self.session.access_token}"
        return headers

    # ── Core chat request ────────────────────────────────────────────

    def _send_chat(self, message: str, name: str = "chat") -> dict | None:
        """Send a message to the chat endpoint and return the response JSON."""
        payload: dict[str, Any] = {"message": message}
        if self.session.session_id:
            payload["session_id"] = self.session.session_id
        if self.session.customer_name:
            payload["customer_name"] = self.session.customer_name

        with self.client.post(
            "/api/agent/chat/",
            json=payload,
            headers=self._auth_headers(),
            catch_response=True,
            name=name,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                response_text = data.get("response", "")
                session_id = data.get("session_id") or data.get("conversation_id")

                if session_id:
                    self.session.session_id = session_id

                # Validate non-empty response
                if response_text:
                    resp.success()
                    self.session.consecutive_failures = 0
                    self.session.messages_sent += 1
                    return data
                else:
                    resp.failure("Empty response from agent")
                    self.session.consecutive_failures += 1
                    return None

            elif resp.status_code == 429:
                # Rate limited — wait longer and retry on next task iteration
                resp.success()  # Don't count as failure, just back off
                self.session.consecutive_failures += 1
                time.sleep(random.uniform(5.0, 10.0))
                return None

            elif resp.status_code == 401:
                # Token expired — try to refresh
                resp.success()
                if self._refresh_token():
                    return self._send_chat(message, name)
                return None

            else:
                resp.failure(f"Chat failed: {resp.status_code} {resp.text[:200]}")
                self.session.consecutive_failures += 1
                return None

    def _check_health(self) -> None:
        """Ping the health endpoint to verify backend is up."""
        with self.client.get(
            "/health/",
            catch_response=True,
            name="00_health",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Health check failed: {resp.status_code}")

    def _check_metrics(self) -> None:
        """Fetch metrics to ensure the endpoint responds."""
        with self.client.get(
            "/metrics/",
            catch_response=True,
            name="00_metrics",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Metrics endpoint failed: {resp.status_code}")

    # ── Tasks ────────────────────────────────────────────────────────

    @task(3)
    def query_menu(self) -> None:
        """Ask about the menu."""
        msg = _pick_message(MENU_QUERIES)
        self._send_chat(msg, "10_menu_query")

    @task(2)
    def place_order(self) -> None:
        """Start or manage an order."""
        msg = _pick_message(ORDER_QUERIES)
        self._send_chat(msg, "20_order_flow")

    @task(1)
    def make_reservation(self) -> None:
        """Check or create a reservation."""
        msg = _pick_message(RESERVATION_QUERIES)
        self._send_chat(msg, "30_reservation_flow")

    @task(2)
    def general_chat(self) -> None:
        """General restaurant Q&A."""
        msg = _pick_message(GENERAL_QUERIES)
        self._send_chat(msg, "40_general_chat")

    @task(1)
    def check_health_endpoint(self) -> None:
        """Smoke-test /health/ (no auth needed)."""
        self._check_health()

    @task(1)
    def check_metrics_endpoint(self) -> None:
        """Smoke-test /metrics/ (no auth needed)."""
        self._check_metrics()

    # ── Edge-case tasks ──────────────────────────────────────────────

    @task(1)
    def empty_message(self) -> None:
        """Send an empty message to test error handling."""
        with self.client.post(
            "/api/agent/chat/",
            json={"message": ""},
            headers=self._auth_headers(),
            catch_response=True,
            name="50_empty_message",
        ) as resp:
            if resp.status_code == 400:
                resp.success()
            else:
                resp.failure(f"Expected 400 for empty message, got {resp.status_code}")

    @task(1)
    def very_long_message(self) -> None:
        """Send a very long message to test input limits."""
        long_msg = "I would like to know " + "very " * 200 + "much about your restaurant"
        self._send_chat(long_msg, "50_long_message")

    @task(1)
    def throttle_test(self) -> None:
        """Send 3 messages in quick succession to verify rate-limit handling.

        This tests that the 429 response is handled gracefully (back-off,
        retry). Latency metrics for this task may be inflated by the
        backoff sleep — this is intentional.
        """
        for msg in ["What's on the menu?", "I'll have a pizza", "Actually make it a burger"][:3]:
            if self.session.consecutive_failures > 5:
                time.sleep(random.uniform(5.0, 10.0))
                break
            self._send_chat(msg, "50_throttle_test")
            time.sleep(random.uniform(0.5, 1.5))


# ── Helper to check results after test ───────────────────────────────────


@events.quitting.add_listener
def on_quit(environment, **_kwargs):
    """Print a summary of results when the test finishes."""
    stats = environment.runner.stats if environment.runner else None
    if not stats:
        return

    total = stats.num_requests
    failures = stats.num_failures
    avg = stats.total.avg_response_time if total else 0

    print("\n" + "=" * 60)
    print("  LOAD TEST SUMMARY")
    print("=" * 60)
    print(f"  Total requests:    {total}")
    print(f"  Failures:          {failures} ({(failures / total * 100) if total else 0:.1f}%)")
    print(f"  Avg response:      {avg:.0f} ms")
    print(f"  RPS (overall):     {stats.total_rps:.1f}")
    print(f"  Current time:      {time.strftime('%H:%M:%S')}")
    print("=" * 60)

    # Print per-endpoint breakdown
    print("\n  Per-endpoint breakdown:")
    for key, entry in sorted(stats.entries.items()):
        method = entry.method
        name = entry.name
        if not name:
            continue
        print(f"    {method:6s} {name:30s} "
              f"n={entry.num_requests:4d}  "
              f"avg={entry.avg_response_time:5.0f}ms  "
              f"fail={entry.num_failures:3d}")
    print()
