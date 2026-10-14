"""Authenticated installation scheduling API."""

from django.shortcuts import get_object_or_404
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .installation_schedule_services import (
    cancel_installation_schedule,
    complete_installation_schedule,
    create_installation_schedule,
)
from .models import InstallationSchedule, Project, Role, User
from .operational_visibility import operational_project_scope


class InstallationScheduleInput(serializers.Serializer):
    project = serializers.UUIDField()
    scheduled_date = serializers.DateField()
    installation_manager = serializers.UUIDField()


class InstallationScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstallationSchedule
        fields = [
            "id",
            "project",
            "scheduled_date",
            "installation_manager",
            "scheduled_by",
            "status",
            "completed_at",
            "cancelled_at",
        ]
        read_only_fields = fields


class InstallationManagerSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name"]
        read_only_fields = fields


class InstallationManagerDirectoryViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = InstallationManagerSerializer
    queryset = User.objects.none()
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        from .installation_schedule_services import _authorized_installation_actor

        _authorized_installation_actor(self.request.user)
        return User.objects.filter(
            is_active=True,
            role=Role.INSTALLATION_MANAGER,
        ).order_by("username", "pk")


class InstallationSchedulePagination(PageNumberPagination):
    page_size = 50


class InstallationScheduleViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = InstallationScheduleSerializer
    pagination_class = InstallationSchedulePagination
    queryset = InstallationSchedule.objects.none()
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return (
            InstallationSchedule.objects
            .filter(project__in=operational_project_scope(self.request.user))
            .select_related("project", "installation_manager", "scheduled_by")
            .order_by("-scheduled_date", "-pk")
        )

    def list(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(
                self.get_serializer(page, many=True).data
            )
        return Response(self.get_serializer(queryset, many=True).data)

    def create(self, request):
        data = InstallationScheduleInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data

        project = get_object_or_404(Project, pk=values["project"])
        manager = get_object_or_404(
            User,
            pk=values["installation_manager"],
            is_active=True,
        )

        schedule = create_installation_schedule(
            actor=request.user,
            project=project,
            scheduled_date=values["scheduled_date"],
            installation_manager=manager,
        )
        return Response(InstallationScheduleSerializer(schedule).data, status=201)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        get_object_or_404(InstallationSchedule, pk=pk)
        schedule = complete_installation_schedule(
            actor=request.user,
            schedule_id=pk,
        )
        return Response(InstallationScheduleSerializer(schedule).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        get_object_or_404(InstallationSchedule, pk=pk)
        schedule = cancel_installation_schedule(
            actor=request.user,
            schedule_id=pk,
        )
        return Response(InstallationScheduleSerializer(schedule).data)

class InstallationReadinessSerializer(serializers.Serializer):
    project_id = serializers.UUIDField()
    eligible = serializers.BooleanField()
    requirements = serializers.DictField()
    blocking_reasons = serializers.ListField()


class InstallationReadinessViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = InstallationReadinessSerializer
    queryset = Project.objects.none()
    http_method_names = ["get", "head", "options"]

    def retrieve(self, request, pk=None):
        project = get_object_or_404(
            operational_project_scope(request.user),
            pk=pk,
        )

        from .installation_readiness import installation_readiness

        result = installation_readiness(project)

        payload = {
            "project_id": project.id,
            **result,
        }

        return Response(
            InstallationReadinessSerializer(payload).data
        )
