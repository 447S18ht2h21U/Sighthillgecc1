"""Unregistered sales-status API candidate.

Never changes operational project state, MSR approval or completion.
Routes remain unregistered pending audit integrity acceptance.
"""
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Project
from .operational_visibility import operational_project_scope
from .sales_status_service_5000 import change_project_sales_status


class SalesStatusInput(serializers.Serializer):
    sales_status = serializers.ChoiceField(
        choices=Project.SalesStatus.choices
    )
    reason = serializers.CharField(
        trim_whitespace=True,
        min_length=10,
        allow_blank=False,
    )


class SalesStatusDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get_project(self, request, project_id):
        visible = operational_project_scope(request.user)
        return get_object_or_404(visible, pk=project_id)

    def get(self, request, project_id):
        project = self.get_project(request, project_id)
        history = list(
            project.sales_status_history
            .order_by("-changed_at", "-pk")
            .values(
                "id",
                "previous_status",
                "new_status",
                "reason",
                "changed_at",
                "changed_by_id",
            )[:100]
        )
        return Response({
            "project_id": str(project.pk),
            "sales_status": project.sales_status,
            "project_state": project.state,
            "history": history,
            "history_limit": 100,
        })

    def post(self, request, project_id):
        project = self.get_project(request, project_id)
        data = SalesStatusInput(data=request.data)
        data.is_valid(raise_exception=True)

        try:
            change = change_project_sales_status(
                actor=request.user,
                project_id=project.pk,
                new_status=data.validated_data["sales_status"],
                reason=data.validated_data["reason"],
            )
        except PermissionDenied:
            return Response(
                {"detail": "Sales status change not authorized."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except ValidationError as exc:
            return Response(
                {"detail": exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project.refresh_from_db()
        return Response({
            "project_id": str(project.pk),
            "sales_status": project.sales_status,
            "project_state": project.state,
            "audit_id": change.pk,
        }, status=status.HTTP_200_OK)
