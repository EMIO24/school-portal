from django.test import TestCase
from rest_framework.test import APIClient

from .models import School


class SchoolLookupTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        School.objects.create(name="Bright Future College", slug="bright-future", subdomain="bright-future")

    def lookup(self, name):
        return self.client.get("/api/school-lookup/", {"name": name})

    def test_exact_case_whitespace_and_unique_partial_names_resolve(self):
        for name in ["Bright Future College", "bright future college", "  Bright   Future College  ", "Bright Future"]:
            response = self.lookup(name)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"found": True, "slug": "bright-future"})

    def test_empty_short_and_unknown_queries_do_not_enumerate(self):
        for name in ["", "Br", "Unknown Academy"]:
            self.assertEqual(self.lookup(name).json(), {"found": False})

    def test_inactive_and_unapproved_schools_are_not_exposed(self):
        School.objects.create(name="Hidden Academy", slug="hidden", subdomain="hidden", is_active=False)
        School.objects.create(name="Pending Academy", slug="pending", subdomain="pending", approval_status="pending")
        self.assertEqual(self.lookup("Hidden Academy").json(), {"found": False})
        self.assertEqual(self.lookup("Pending Academy").json(), {"found": False})

    def test_ambiguous_match_never_selects_a_tenant(self):
        School.objects.create(name="Bright Future Academy", slug="bright-academy", subdomain="bright-academy")
        self.assertEqual(self.lookup("Bright Future").json(), {"found": False, "ambiguous": True})

    def test_response_exposes_only_resolution_fields(self):
        data = self.lookup("Bright Future College").json()
        self.assertEqual(set(data), {"found", "slug"})
        self.assertNotIn("id", data)
        self.assertNotIn("email", data)
