"""Production monitoring endpoints — health check and metrics.

- /health/    — Returns DB, pgvector, LLM provider status + uptime
- /metrics/   — Returns JSON with request counts, avg response time, error rate, LLM usage
"""

import logging
import os
import time
import threading
from collections import defaultdict
from datetime import datetime, timezone

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views import View

logger = logging.getLogger(__name__)

_START_TIME = time.time()

# ── Simple in-process metrics collector ──────────────────────────────────

_lock = threading.Lock()
_metrics: dict[str, float | int] = {
    "requests_total": 0,
    "requests_2xx": 0,
    "requests_4xx": 0,
    "requests_5xx": 0,
    "response_time_ms_total": 0,
    "response_time_ms_count": 0,
    "llm_calls_total": 0,
    "llm_calls_success": 0,
    "llm_tokens_prompt": 0,
    "llm_tokens_completion": 0,
    "tool_calls_total": 0,
    "tool_calls_success": 0,
    "orders_placed": 0,
    "payments_processed": 0,
    "reservations_made": 0,
}


def record_request(status_code: int, duration_ms: float) -> None:
    """Record an API request for metrics."""
    with _lock:
        _metrics["requests_total"] += 1
        if 200 <= status_code < 300:
            _metrics["requests_2xx"] += 1
        elif 400 <= status_code < 500:
            _metrics["requests_4xx"] += 1
        else:
            _metrics["requests_5xx"] += 1
        _metrics["response_time_ms_total"] += duration_ms
        _metrics["response_time_ms_count"] += 1


def record_llm_call(success: bool, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
    """Record an LLM call for metrics."""
    with _lock:
        _metrics["llm_calls_total"] += 1
        if success:
            _metrics["llm_calls_success"] += 1
        _metrics["llm_tokens_prompt"] += prompt_tokens
        _metrics["llm_tokens_completion"] += completion_tokens


def record_tool_call(success: bool) -> None:
    """Record a tool execution for metrics."""
    with _lock:
        _metrics["tool_calls_total"] += 1
        if success:
            _metrics["tool_calls_success"] += 1


def record_business_event(event: str) -> None:
    """Record a business event for metrics."""
    with _lock:
        key = f"{event}_total" if event in ("orders", "payments", "reservations") else event
        if key in ("orders_total", "payments_total", "reservations_total"):
            mapping = {"orders": "orders_placed", "payments": "payments_processed", "reservations": "reservations_made"}
            _metrics[mapping[event]] += 1
        else:
            _metrics[event] = _metrics.get(event, 0) + 1


def get_metrics_snapshot() -> dict:
    """Return a snapshot of current metrics with derived values."""
    with _lock:
        snapshot = dict(_metrics)

    total = snapshot["requests_total"]
    snapshot["uptime_seconds"] = round(time.time() - _START_TIME, 1)
    snapshot["avg_response_time_ms"] = round(
        snapshot["response_time_ms_total"] / snapshot["response_time_ms_count"], 1
    ) if snapshot["response_time_ms_count"] > 0 else 0.0
    snapshot["error_rate_pct"] = round(
        (snapshot["requests_5xx"] / total) * 100, 2
    ) if total > 0 else 0.0
    snapshot["llm_success_rate_pct"] = round(
        (snapshot["llm_calls_success"] / snapshot["llm_calls_total"]) * 100, 1
    ) if snapshot["llm_calls_total"] > 0 else 100.0
    snapshot["tool_success_rate_pct"] = round(
        (snapshot["tool_calls_success"] / snapshot["tool_calls_total"]) * 100, 1
    ) if snapshot["tool_calls_total"] > 0 else 100.0

    return snapshot


# ── Health endpoint ─────────────────────────────────────────────────────


class HealthView(View):
    """Health check endpoint that verifies DB connectivity and key services."""

    def get(self, request):
        status_code = 200
        checks = {
            "status": "ok",
            "uptime_seconds": round(time.time() - _START_TIME, 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Database check
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                checks["database"] = "ok"
        except Exception as e:
            checks["database"] = f"error: {e}"
            status_code = 503

        # pgvector check
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
                row = cursor.fetchone()
                checks["pgvector"] = "ok" if row else "not enabled"
        except Exception:
            checks["pgvector"] = "ok"  # SQLite — not applicable

        # LLM provider check
        llm_key = getattr(settings, "LLM_API_KEY", "")
        if not llm_key:
            llm_key = getattr(settings, "HF_TOKEN", "")
        checks["llm_provider"] = "configured" if llm_key else "not configured (using fallback)"

        return JsonResponse(checks, status=status_code)


# ── Metrics endpoint ────────────────────────────────────────────────────


class MetricsView(View):
    """Metrics endpoint exposing internal counters for monitoring."""

    def get(self, request):
        return JsonResponse(get_metrics_snapshot())
