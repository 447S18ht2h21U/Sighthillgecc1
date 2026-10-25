"""Authenticated API operations for technical project assignments."""

from django.shortcuts import get_object_or_404
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Project, ProjectTechnicalAssignment, Role, User
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


class TechnicalAssignmentHistoryPagination(
    __import__("rest_framework.pagination", fromlist=["PageNumberPagination"]).PageNumberPagination
):
    page_size = 50


class TechnicalAssignmentHistorySerializer(serializers.ModelSerializer):
    technician_username = serializers.CharField(
        source="technical_associate.username",
        read_only=True,
    )
    technician_first_name = serializers.CharField(
        source="technical_associate.first_name",
        read_only=True,
    )
    technician_last_name = serializers.CharField(
        source="technical_associate.last_name",
        read_only=True,
    )

    class Meta:
        model = ProjectTechnicalAssignment
        fields = [
            "id",
            "project",
            "technical_associate",
            "technician_username",
            "technician_first_name",
            "technician_last_name",
            "assigned_by",
            "effective_date",
            "status",
            "ended_at",
        ]
        read_only_fields = fields


class TechnicalAssignmentHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Project-scoped Technician assignment history."""

    from rest_framework.permissions import IsAuthenticated

    permission_classes = [IsAuthenticated]
    serializer_class = TechnicalAssignmentHistorySerializer
    pagination_class = TechnicalAssignmentHistoryPagination
    http_method_names = ["get", "head", "options"]
    queryset = ProjectTechnicalAssignment.objects.none()

    def get_queryset(self):
        from rest_framework.exceptions import PermissionDenied, ValidationError
        from .operational_visibility import operational_project_scope

        actor = User.objects.filter(
            pk=self.request.user.pk,
            is_active=True,
        ).first()

        if actor is None or actor.role not in (
            Role.INSTALLATION_MANAGER,
            Role.CEO,
            Role.COMPTROLLER,
        ):
            raise PermissionDenied(
                "Only an Installation Manager, CEO, or Comptroller may view Technician assignment history."
            )

        project_id = self.request.query_params.get("project")

        if not project_id:
            raise ValidationError({
                "project": "Select a project to view Technician assignment history."
            })

        project_field = serializers.UUIDField()

        try:
            project_id = project_field.run_validation(project_id)
        except serializers.ValidationError:
            raise ValidationError({
                "project": "Select a valid project."
            })

        if not operational_project_scope(actor).filter(pk=project_id).exists():
            raise PermissionDenied(
                "You do not have access to Technician assignment history for this project."
            )

        return (
            ProjectTechnicalAssignment.objects
            .filter(project_id=project_id)
            .select_related("technical_associate", "assigned_by")
            .order_by("-effective_date", "-created_at", "-pk")
        )

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response

class TechnicianDirectorySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name"]
        read_only_fields = fields


class TechnicianDirectoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Active Technician directory restricted to approved permanent roles."""

    from rest_framework.permissions import IsAuthenticated
    permission_classes = [IsAuthenticated]
    serializer_class = TechnicianDirectorySerializer
    queryset = User.objects.none()
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        from rest_framework.exceptions import PermissionDenied

        actor = User.objects.filter(
            pk=self.request.user.pk,
            is_active=True,
        ).first()

        if actor is None or actor.role not in (
            Role.INSTALLATION_MANAGER,
            Role.CEO,
            Role.COMPTROLLER,
        ):
            raise PermissionDenied(
                "Only an Installation Manager, CEO, or Comptroller may view the Technician directory."
            )

        return User.objects.filter(
            is_active=True,
            role=Role.TECHNICIAN,
        ).order_by("last_name", "first_name", "username", "pk")
