"""Dedicated role-scoped, read-only MSR API foundation.

Registered as the read-only visible-msrs API after security testing.

No editing, approval, document generation, signing, or financial
reporting actions are provided by this ViewSet.
"""

from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from .access_msr_project_scope import msr_visible_project_scope
from .access_msr_visibility_policy import msr_read_scope
from .api import Page
from .marketing_msr_api import MarketingMSRSerializer
from .models import MSR, User


class VisibleMSRViewSet(viewsets.ReadOnlyModelViewSet):
    """Return permitted MSR records without mutation authority."""

    serializer_class = MarketingMSRSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Page
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        request = self.request
        actor = getattr(request, "user", None)

        if (
            actor is None
            or not getattr(actor, "is_authenticated", False)
            or getattr(actor, "pk", None) is None
        ):
            raise PermissionDenied("An active account is required.")

        verified_actor = (
            User.objects
            .filter(pk=actor.pk, is_active=True)
            .first()
        )

        if verified_actor is None:
            raise PermissionDenied("An active account is required.")

        if msr_read_scope(
            verified_actor,
            action=self.action,
            method=request.method,
        ) is None:
            raise PermissionDenied("MSR viewing is not authorized.")

        projects = msr_visible_project_scope(
            verified_actor,
            action=self.action,
            method=request.method,
        )

        return (
            MSR.objects
            .filter(project__in=projects)
            .order_by("-created_at", "-id")
        )

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(
            request, response, *args, **kwargs
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response