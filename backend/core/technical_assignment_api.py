"""Authenticated API operations for technical project assignments."""

from django.shortcuts import get_object_or_404
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Project, ProjectTechnicalAssignment, User
from .technical_assignment_services import create_technical_assignment, end_technical_assignment


class TechnicalAssignmentInput(serializers.Serializer):
    project = serializers.UUIDField()
    technical_associate = serializers.UUIDField()
    effective_date = serializers.DateField()


class TechnicalAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectTechnicalAssignment
        fields = [
            "id",
            "project",
            "technical_associate",
            "assigned_by",
            "effective_date",
            "status",
            "ended_at",
        ]
        read_only_fields = fields


class TechnicalAssignmentViewSet(viewsets.GenericViewSet):
    serializer_class = TechnicalAssignmentSerializer
    queryset = ProjectTechnicalAssignment.objects.none()
    http_method_names = ["post", "head", "options"]

    def create(self, request):
        data = TechnicalAssignmentInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data

        project = get_object_or_404(Project, pk=values["project"])
        technician = get_object_or_404(
            User,
            pk=values["technical_associate"],
            is_active=True,
        )

        assignment = create_technical_assignment(
            actor=request.user,
            project=project,
            technical_associate=technician,
            effective_date=values["effective_date"],
        )

        return Response(
            TechnicalAssignmentSerializer(assignment).data,
            status=201,
        )

    @action(detail=True, methods=["post"], url_path="end")
    def end_assignment(self, request, pk=None):
        get_object_or_404(ProjectTechnicalAssignment, pk=pk)

        assignment = end_technical_assignment(
            actor=request.user,
            assignment_id=pk,
        )

        return Response(
            TechnicalAssignmentSerializer(assignment).data,
            status=200,
        )
