import logging
import re
import time
import uuid
import threading

from config.monitoring import record_request

THREADLOCAL_KEY = "request_id"

logger = logging.getLogger(__name__)

# ── Input sanitization patterns ─────────────────────────────────────────

# Detect common prompt injection attempts
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|above|the\s+above)\s+instructions", re.I),
    re.compile(r"forget\s+(everything|all\s+previous)", re.I),
    re.compile(r"system\s+prompt", re.I),
    re.compile(r"you\s+are\s+(not\s+)?(an?\s+)?(AI|assistant|chatbot|bot)", re.I),
    re.compile(r"override\s+(mode|instructions|rules)", re.I),
    re.compile(r"disregard\s+(all\s+)?(previous|instructions)", re.I),
    re.compile(r"reset\s+(conversation|chat|session)", re.I),
    re.compile(r"act\s+as\s+(if\s+)?(you\s+are\s+)?", re.I),
    re.compile(r"role\s*(play|playing)", re.I),
    re.compile(r"<[^>]+>.*?</[^>]+>", re.DOTALL),  # HTML/XML tags used for injection
]

MAX_MESSAGE_LENGTH = 5000


def sanitize_message(message: str) -> str:
    """Sanitize a user message before it reaches the LLM.

    - Truncates to MAX_MESSAGE_LENGTH characters
    - Strips HTML/XML tags commonly used for injection
    - Returns the cleaned message and whether injection was detected
    """
    if not message:
        return message

    cleaned = message[:MAX_MESSAGE_LENGTH]

    # Strip HTML/XML tags (most common injection vector)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)

    # Detect injection attempts (for logging, not blocking)
    for pattern in INJECTION_PATTERNS:
        if pattern.search(cleaned):
            logger.warning("Potential prompt injection detected: pattern=%s message=%r",
                           pattern.pattern[:40], cleaned[:100])

    return cleaned


def sanitize_messages(messages: list[dict]) -> list[dict]:
    """Sanitize all user messages in a message list."""
    result = []
    for msg in messages:
        if msg.get("role") == "user" and msg.get("content"):
            msg = dict(msg)
            msg["content"] = sanitize_message(msg["content"])
        result.append(msg)
    return result


# ── Request ID filter ───────────────────────────────────────────────────


class RequestIDFilter(logging.Filter):
    """Inject request_id into every log record."""

    def filter(self, record):
        record.request_id = getattr(threading.local(), THREADLOCAL_KEY, "-")[:8]
        return True


class RequestIDMiddleware:
    """Attach a short UUID + timing to each request for log correlation and metrics."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import threading

        rid = uuid.uuid4().hex[:8]
        setattr(threading.local(), THREADLOCAL_KEY, rid)
        request.request_id = rid
        start = time.time()

        response = self.get_response(request)

        duration_ms = (time.time() - start) * 1000
        response["X-Request-ID"] = rid
        response["X-Request-Time-Ms"] = str(round(duration_ms, 1))

        # Record metrics (exclude health/metrics endpoints to avoid noise)
        path = request.path.rstrip("/")
        if path not in ("/health", "/metrics"):
            record_request(response.status_code, duration_ms)

        return response
