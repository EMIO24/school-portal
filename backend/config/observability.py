import logging
import uuid

from django.utils.deprecation import MiddlewareMixin


logger = logging.getLogger("paideia.request")


class RequestIDMiddleware(MiddlewareMixin):
    """Attach a correlation ID without recording request data or credentials."""

    def process_request(self, request):
        request.request_id = uuid.uuid4().hex

    def process_response(self, request, response):
        response["X-Request-ID"] = getattr(request, "request_id", uuid.uuid4().hex)
        return response

    def process_exception(self, request, exception):
        logger.error(
            "request_failed request_id=%s method=%s path=%s error_type=%s",
            getattr(request, "request_id", "unavailable"),
            request.method,
            request.path,
            type(exception).__name__,
        )
        return None
