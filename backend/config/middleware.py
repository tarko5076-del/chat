import logging
import uuid

THREADLOCAL_KEY = "request_id"


class RequestIDFilter(logging.Filter):
    """Inject request_id into every log record."""

    def filter(self, record):
        import threading

        record.request_id = getattr(threading.local(), THREADLOCAL_KEY, "-")[:8]
        return True


class RequestIDMiddleware:
    """Attach a short UUID to each request for log correlation."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import threading

        rid = uuid.uuid4().hex[:8]
        setattr(threading.local(), THREADLOCAL_KEY, rid)
        request.request_id = rid
        response = self.get_response(request)
        response["X-Request-ID"] = rid
        return response
