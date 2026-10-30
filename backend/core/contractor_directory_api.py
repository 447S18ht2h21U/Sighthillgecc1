"""Restricted, read-only VERIDIAN contractor directory API."""

from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from .models import Contractor, ContractorEngagement, Role, User


class ContractorDirectoryPagination(PageNumberPagination):
    page_size = 50
    max_page_size = 50


class ContractorEngagementDirectorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractorEngagement
        fields = [
            "id",
            "engagement_code",
            "role_description",
            "start_date",
            "end_date",
            "status",
        ]
        read_only_fields = fields


class ContractorDirectorySerializer(serializers.ModelSerializer):
    engagements = ContractorEngagementDirectorySerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = Contractor
        fields = [
            "id",
            "contractor_number",
            "legal_name",
            "engagements",
        ]
        read_only_fields = fields


class ContractorDirectoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Minimal contractor directory for active CEO and Comptroller users."""

    permission_classes = [IsAuthenticated]
    serializer_class = ContractorDirectorySerializer
    pagination_class = ContractorDirectoryPagination
    http_method_names = ["get", "head", "options"]
    queryset = Contractor.objects.none()

    def get_queryset(self):
        actor = User.objects.filter(
            pk=self.request.user.pk,
            is_active=True,
        ).first()

        if actor is None or actor.role not in (
            Role.CEO,
            Role.COMPTROLLER,
        ):
            raise PermissionDenied(
                "Only an active CEO or Comptroller may view "
                "the Contractor Directory."
            )

        return (
            Contractor.objects
            .prefetch_related("engagements")
            .order_by("contractor_number", "pk")
        )

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(
            request, response, *args, **kwargs
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response