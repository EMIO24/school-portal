from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from .observability import RequestIDMiddleware


class RequestObservabilityTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = RequestIDMiddleware(lambda request: HttpResponse("ok"))

    def test_request_id_is_returned_and_unique(self):
        first = self.middleware(self.factory.get("/health/"))["X-Request-ID"]
        second = self.middleware(self.factory.get("/health/"))["X-Request-ID"]
        self.assertEqual(len(first), 32)
        self.assertNotEqual(first, second)

    def test_exception_log_excludes_headers_query_and_exception_message(self):
        secret = "SENSITIVE_TEST_VALUE"
        request = self.factory.get("/api/example/?password=" + secret, HTTP_AUTHORIZATION="Bearer " + secret)
        self.middleware.process_request(request)
        with self.assertLogs("paideia.request", level="ERROR") as captured:
            self.middleware.process_exception(request, RuntimeError(secret))
        output = " ".join(captured.output)
        self.assertIn("request_failed", output)
        self.assertIn("error_type=RuntimeError", output)
        self.assertNotIn(secret, output)

    def test_health_response_exposes_only_status(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
