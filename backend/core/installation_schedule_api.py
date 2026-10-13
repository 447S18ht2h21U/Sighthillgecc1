"""Authenticated installation scheduling API."""

from django.shortcuts import get_object_or_404
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .installation_schedule_services import (
    cancel_installation_schedule,
    complete_installation_schedule,
    create_installation_schedule,
)
from .models import InstallationSchedule, Project, User


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


class InstallationScheduleViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = InstallationScheduleSerializer
    queryset = InstallationSchedule.objects.none()
    http_method_names = ["post", "head", "options"]

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