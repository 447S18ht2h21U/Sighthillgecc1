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
    installation_manager_display = serializers.SerializerMethodField()

    def get_installation_manager_display(self, obj):
        manager = obj.installation_manager
        full_name = f'{manager.first_name} {manager.last_name}'.strip()
        return f'{full_name} ({manager.username})' if full_name else manager.username
    class Meta:
        model = InstallationSchedule
        fields = [
            "id",
            "project",
            "scheduled_date",
            "installation_manager",
            "installation_manager_display",
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


    @action(detail=False, methods=["post"], url_path="assess-proposed-date")
    def assess_proposed_date(self, request):
        """Read-only assessment; does not grant scheduling or start authority."""
        from django.utils import timezone
        from rest_framework.exceptions import ValidationError
        from .installation_schedule_services import _authorized_installation_actor
        from .installation_eligibility import (
            require_current_approved_msr,
            verified_signature_time,
            cancellation_deadline,
        )
        from .installation_payment_readiness import installation_payment_readiness
        from .installation_future_date_policy_4565 import assess_future_installation_date
        from .models import CustomerSignatureEvidence

        actor, _ = _authorized_installation_actor(request.user)
        class AssessmentInput(serializers.Serializer):
            project = serializers.UUIDField()
            scheduled_date = serializers.DateField()

        values = AssessmentInput(data=request.data)
        values.is_valid(raise_exception=True)
        project = get_object_or_404(
            operational_project_scope(actor), pk=values.validated_data["project"]
        )
        msr = require_current_approved_msr(project)
        signed = verified_signature_time(
            msr, CustomerSignatureEvidence.DocumentKind.CONTRACT
        )
        deadline = cancellation_deadline(msr)
        try:
            result = assess_future_installation_date(
                proposed_date=values.validated_data["scheduled_date"],
                verified_contract_signed_at=signed,
                verified_cancellation_deadline=deadline,
                now=timezone.now(),
            )
        except ValueError as exc:
            raise ValidationError({"scheduled_date": str(exc)}) from exc

        payment = installation_payment_readiness(project)
        return Response({
            "project_id": str(project.pk),
            "scheduled_date": values.validated_data["scheduled_date"].isoformat(),
            "normal_date_eligible": result["normal_date_eligible"],
            "payment_ready": payment["payment_ready"],
            "scheduling_candidate": (
                result["normal_date_eligible"] and payment["payment_ready"]
            ),
            "earliest_normal_installation_at": result["earliest_at"].isoformat(),
            "payment_explanation": payment["explanation"],
            "installation_authorized": False,
            "installation_started": False,
            "expedited_authorized": False,
        })

    @action(detail=False, methods=["post"], url_path="schedule-future")
    def schedule_future(self, request):
        """Create a future appointment after server-side evidence checks."""
        from .installation_schedule_services import (
            create_future_installation_schedule,
        )
        from .installation_schedule_services import _authorized_installation_actor

        actor, _ = _authorized_installation_actor(request.user)
        fields = InstallationScheduleInput(data=request.data)
        fields.is_valid(raise_exception=True)
        values = fields.validated_data

        project = get_object_or_404(
            operational_project_scope(actor), pk=values["project"]
        )
        manager = get_object_or_404(
            User,
            pk=values["installation_manager"],
            is_active=True,
            role=Role.INSTALLATION_MANAGER,
        )
        schedule = create_future_installation_schedule(
            actor=actor,
            project=project,
            scheduled_date=values["scheduled_date"],
            installation_manager=manager,
        )
        return Response(
            InstallationScheduleSerializer(schedule).data,
            status=201,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="request-expedited",
        url_name="request-expedited",
    )
    def request_expedited_service(self, request):
        """Record a pending claim; never authorize an installation."""
        from .expedited_service_request_4565 import record_expedited_service_request
        from .installation_schedule_services import _authorized_installation_actor

        class RequestInput(serializers.Serializer):
            project = serializers.UUIDField()
            proposed_date = serializers.DateField()
            reason = serializers.CharField(min_length=15, max_length=2000)
            document_reference = serializers.CharField(min_length=5, max_length=250)

        actor, _ = _authorized_installation_actor(request.user)
        fields = RequestInput(data=request.data)
        fields.is_valid(raise_exception=True)
        values = fields.validated_data

        project = get_object_or_404(
            operational_project_scope(actor), pk=values["project"]
        )

        evidence = record_expedited_service_request(
            actor=actor,
            project_id=project.pk,
            proposed_date=values["proposed_date"],
            reason=values["reason"],
            document_reference=values["document_reference"],
        )
        return Response({
            "evidence_id": str(evidence.pk),
            "status": "PENDING_INDEPENDENT_VERIFICATION",
            "expedited_authorized": False,
            "installation_authorized": False,
        }, status=201)

    @action(
        detail=False,
        methods=["post"],
        url_path="review-expedited",
        url_name="review-expedited",
    )
    def review_expedited_service(self, request):
        """Independent candidate review; never grants installation authority."""
        from .expedited_service_review_4565 import (
            review_expedited_service_request,
        )

        class ReviewInput(serializers.Serializer):
            request_id = serializers.UUIDField()
            accept_candidate = serializers.BooleanField()
            review_reason = serializers.CharField(
                min_length=15, max_length=2000
            )

        fields = ReviewInput(data=request.data)
        fields.is_valid(raise_exception=True)
        values = fields.validated_data

        decision = review_expedited_service_request(
            actor=request.user,
            request_id=values["request_id"],
            accept_candidate=values["accept_candidate"],
            review_reason=values["review_reason"],
        )

        return Response({
            "decision_id": str(decision.pk),
            "status": decision.data["status"],
            "expedited_authorized": False,
            "installation_authorized": False,
        }, status=201)

    @action(
        detail=False,
        methods=["post"],
        url_path="assess-start",
        url_name="assess-start",
    )
    def assess_installation_start(self, request):
        """Evaluate live records; never create installation-start authority."""
        from .installation_schedule_services import _authorized_installation_actor
        from .installation_start_control_4565 import assess_installation_start

        class StartAssessmentInput(serializers.Serializer):
            project = serializers.UUIDField()
            proposed_start = serializers.DateTimeField()

        actor, _ = _authorized_installation_actor(request.user)
        fields = StartAssessmentInput(data=request.data)
        fields.is_valid(raise_exception=True)
        values = fields.validated_data
        project = get_object_or_404(
            operational_project_scope(actor),
            pk=values["project"],
        )
        result = assess_installation_start(
            project=project,
            proposed_start=values["proposed_start"],
        )
        return Response(result, status=200)

    @action(
        detail=False,
        methods=["post"],
        url_path="decide-expedited",
        url_name="decide-expedited",
    )
    def decide_expedited_service(self, request):
        from .expedited_manager_decision_4565 import decide_expedited_service_request

        class DecisionInput(serializers.Serializer):
            review_id = serializers.UUIDField()
            approve = serializers.BooleanField()
            decision_reason = serializers.CharField(
                min_length=15, max_length=2000
            )

        fields = DecisionInput(data=request.data)
        fields.is_valid(raise_exception=True)
        decision = decide_expedited_service_request(
            actor=request.user,
            **fields.validated_data,
        )
        return Response({
            "decision_id": str(decision.pk),
            "status": decision.data["status"],
            "expedited_authorized": False,
            "installation_authorized": False,
        }, status=201)

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
