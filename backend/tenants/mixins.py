"""
tenants/mixins.py

TenantMixin — a DRF ViewSet mixin that automatically scopes every queryset
to the current request's tenant (School) and injects `school` on create.

Usage:
    class StudentViewSet(TenantMixin, viewsets.ModelViewSet):
        serializer_class = StudentSerializer
        queryset = Student.objects.all()   # will be filtered automatically

IMPORTANT:
  Every ViewSet in this project MUST inherit TenantMixin (or replicate its
  logic) to satisfy the multi-tenancy guarantee.
"""

from rest_framework.exceptions import PermissionDenied


class TenantMixin:
    """
    Mixin for DRF ModelViewSet subclasses.

    Guarantees:
      - get_queryset()     → always filtered to request.tenant
      - perform_create()   → always sets school = request.tenant
    """

    def _get_tenant(self):
        """
        Return the current tenant or raise PermissionDenied.

        A missing tenant means TenantMiddleware did not resolve a school
        (e.g., request came from the bare apex domain).
        """
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            raise PermissionDenied(
                "No school tenant found for this request. "
                "Ensure you are accessing via a school subdomain."
            )
        return tenant

    # ── Queryset scoping ──────────────────────────────────────────────────────

    def get_queryset(self):
        """
        Override get_queryset to scope results to the current tenant.

        Calls super().get_queryset() so that any further filtering defined
        in child ViewSets (e.g., filter_backends, search_fields) is preserved.
        """
        tenant = self._get_tenant()
        qs = super().get_queryset()
        return qs.filter(school=tenant)

    # ── Object creation ───────────────────────────────────────────────────────

    def perform_create(self, serializer):
        """
        Inject school=request.tenant into every new object.

        Child ViewSets that override perform_create MUST call
        super().perform_create(serializer) or manually set school.
        """
        tenant = self._get_tenant()
        serializer.save(school=tenant)

    # ── Optional: update / partial_update safety ──────────────────────────────

    def perform_update(self, serializer):
        """
        Prevent accidentally moving an object to a different school on update.
        The school field is always kept as the current tenant.
        """
        tenant = self._get_tenant()
        serializer.save(school=tenant)