"""Marketing-only read access to Master Sales Records.

Registered as a dedicated, read-only Marketing endpoint.
No write, document-generation, signing, or approval actions.
"""

from types import SimpleNamespace

from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from .access_marketing_msr_policy import marketing_msr_read_permitted
from .api import Page
from .services import SNAPSHOT_FIELDS
from .models import MSR, Role, User


class MarketingMSRSerializer(serializers.ModelSerializer):
    """Expose only approved commercial MSR fields to Marketing."""

    snapshot = serializers.SerializerMethodField()

    class Meta:
        model = MSR
        fields = [
            "id",
            "number",
            "status",
            "snapshot",
            "created_by",
            "source",
            "revision_reason",
            "edit_sequence",
            "submitted_at",
            "approved_at",
            "approved_by",
        ]
        read_only_fields = fields

    def get_snapshot(self, obj):
        source = obj.snapshot
        if not isinstance(source, dict):
            return {}
        return {
            key: source[key]
            for key in sorted(SNAPSHOT_FIELDS)
            if key in source
        }


class MarketingMSRViewSet(viewsets.ReadOnlyModelViewSet):
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
            raise PermissionDenied("An active Marketing account is required.")

        stored_role = (
            User.objects
            .filter(pk=actor.pk, is_active=True)
            .values_list("role", flat=True)
            .first()
        )

        verified_actor = SimpleNamespace(
            is_authenticated=True,
            is_active=stored_role is not None,
            role=stored_role,
        )

        if not marketing_msr_read_permitted(
            verified_actor,
            action=self.action,
            method=request.method,
        ):
            raise PermissionDenied("Marketing MSR viewing is not authorized.")

        return MSR.objects.all().order_by("-created_at", "-id")

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(
            request, response, *args, **kwargs
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response