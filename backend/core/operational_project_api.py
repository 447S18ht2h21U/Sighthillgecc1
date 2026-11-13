from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from .models import Project, User
from .operational_visibility import operational_project_scope

class OperationalProjectSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.legal_name', read_only=True)
    class Meta:
        model = Project
        fields = ['id', 'code', 'customer', 'customer_name', 'location', 'sales_associate', 'state', 'created_at']
        read_only_fields = fields

class OperationalProjectPagination(PageNumberPagination):
    page_size = 50

class OperationalProjectViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OperationalProjectSerializer
    pagination_class = OperationalProjectPagination
    http_method_names = ['get', 'head', 'options']
    queryset = Project.objects.none()

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Project.objects.none()
        actor = User.objects.filter(pk=user.pk, is_active=True).first()
        if actor is None:
            return Project.objects.none()
        return operational_project_scope(actor).select_related('customer').order_by('-created_at', '-id')



    @action(
        detail=True,
        methods=["get"],
        url_path="installation-eligibility",
    )
    def installation_eligibility(self, request, pk=None):
        project = self.get_object()

        from .installation_readiness import installation_readiness

        result = installation_readiness(project)

        # Read-only evidence visibility; never installation authorization.
        from .models import (
            ExpeditedSigningAttempt,
            ExpeditedEnvelopeBinding,
            ExpeditedSigningObservation,
            ExpeditedSigningDocument,
        )

        from django.db import connections, router

        # Read-only schema check. Missing tables must not cause an HTTP 500
        # or be mistaken for verified expedited-service evidence.
        database_alias = router.db_for_read(ExpeditedSigningAttempt)
        connection = connections[database_alias]
        required_tables = {
            ExpeditedSigningAttempt._meta.db_table,
            ExpeditedEnvelopeBinding._meta.db_table,
            ExpeditedSigningObservation._meta.db_table,
            ExpeditedSigningDocument._meta.db_table,
        }
        with connection.cursor() as cursor:
            existing_tables = set(
                connection.introspection.table_names(cursor)
            )
        storage_available = required_tables.issubset(existing_tables)

        msr = project.current_approved
        attempted = False
        retained = False
        document_count = 0

        if storage_available and msr is not None and msr.status == "APPROVED":
            attempted = ExpeditedSigningAttempt.objects.filter(
                msr=msr
            ).exists()
            observations = ExpeditedSigningObservation.objects.filter(
                binding__attempt__msr=msr
            )
            retained = observations.exists()
            if retained:
                document_count = ExpeditedSigningDocument.objects.filter(
                    observation__in=observations
                ).count()

        result["expedited_service"] = {
            "status": (
                "SCHEMA_UNAVAILABLE"
                if not storage_available else
                "UNVERIFIED_DOCUMENTS_RETAINED"
                if retained else
                "ATTEMPT_RECORDED_UNVERIFIED"
                if attempted else
                "NO_RETAINED_EVIDENCE"
            ),
            "storage_available": storage_available,
            "attempt_recorded": attempted,
            "documents_retained": retained,
            "retained_document_count": document_count,
            "provider_authenticated": False,
            "signatures_verified": False,
            "distribution_verified": False,
            "expedited_authorized": False,
            "installation_authorized": False,
        }

        # Read-only current-time start assessment.
        from django.utils import timezone
        from .installation_start_control_4565 import (
            assess_installation_start,
        )

        result["installation_start"] = assess_installation_start(
            project=project,
            proposed_start=timezone.now(),
        )

        return Response({
            "project_id": project.id,
            **result,
        })

    @action(
        detail=True,
        methods=["get"],
        url_path="completion-preflight",
    )
    def completion_preflight(self, request, pk=None):
        """Authorized, read-only administrative completion assessment."""
        from dataclasses import asdict
        from django.db import connections, router
        from rest_framework.exceptions import PermissionDenied
        from .models import (
            CompletionEnvelopeAttempt,
            CompletionSignatureVerification,
            Document,
            ProjectEvidence,
        )
        from .project_completion_preflight import (
            assess_project_completion_preflight,
        )
        from .services import authorize
        from .receipt_evidence_chain_4613 import inspect_receipt_chain
        from .models import ReceiptDispatchOutbox, ReceiptSendingObservation
        from .completion_evidence_status_4609 import (
            completion_evidence_requirements,
        )

        # Resolve the project through the existing visibility boundary.
        project = self.get_object()
        actor = User.objects.filter(
            pk=request.user.pk,
            is_active=True,
        ).first()
        if actor is None:
            raise PermissionDenied("Active completion reviewer required.")

        # Completion-review authority is separate from project visibility.
        # Deny before disclosing any evidence or database schema details.
        authorize(actor, project, approval=True)

        # Prerequisites are reported read-only to authorized reviewers.
        # No evidence is authenticated and no completion is authorized.
        approved = project.current_approved
        if project.state == "CANCELLED" or (
            approved is None
            or approved.status != "APPROVED"
            or approved.project_id != project.pk
        ):
            reason = (
                "Cancelled projects cannot be completed."
                if project.state == "CANCELLED"
                else "A current approved Master Sales Record is required."
            )
            return Response({
                "project_id": str(project.pk),
                "status": "COMPLETION_PREREQUISITES_MISSING",
                "read_only": True,
                "evidence_requirements": completion_evidence_requirements(project),
                "completion_authorized": False,
                "project_completed": False,
                "receipt_email_authenticated": False,
                "docusign_completion_authenticated": False,
                "satisfaction_survey_required": False,
                "blockers": [
                    reason,
                    "Completion evidence has not been authenticated.",
                    "The authorized project-completion transaction is unavailable.",
                ],
            })

        required_models = (
            ReceiptDispatchOutbox,
            ReceiptSendingObservation,
            CompletionEnvelopeAttempt,
            CompletionSignatureVerification,
            Document,
            ProjectEvidence,
        )
        alias = router.db_for_read(CompletionSignatureVerification)
        connection = connections[alias]
        with connection.cursor() as cursor:
            available = set(connection.introspection.table_names(cursor))

        if not all(
            model._meta.db_table in available
            for model in required_models
        ):
            return Response({
                "project_id": str(project.pk),
                "status": "EVIDENCE_STORAGE_UNAVAILABLE",
                "read_only": True,
                "evidence_requirements": completion_evidence_requirements(project),
                "completion_authorized": False,
                "project_completed": False,
                "receipt_email_authenticated": False,
                "docusign_completion_authenticated": False,
                "satisfaction_survey_required": False,
                "blockers": [
                    "Completion evidence storage is unavailable; "
                    "database migration and verification are pending."
                ],
            })

        report = assess_project_completion_preflight(
            actor=actor,
            project_id=project.pk,
        )
        result = asdict(report)

        # This API cannot grant or represent completion authority.
        if (
            result["completion_authorized"] is not False
            or result["project_completed"] is not False
            or result["receipt_email_authenticated"] is not False
            or result["docusign_completion_authenticated"] is not False
            or result["satisfaction_survey_required"] is not False
        ):
            raise PermissionDenied(
                "Unverified completion authority is prohibited."
            )

        return Response({
            **result,
            "status": "COMPLETION_EVIDENCE_UNVERIFIED",
            "read_only": True,
            "receipt_evidence": inspect_receipt_chain(project),
            "evidence_requirements": completion_evidence_requirements(project, report),
        })

    @action(
        detail=True,
        methods=["get"],
        url_path="completion-signature-status",
    )
    def completion_signature_status(self, request, pk=None):
        """Read-only administrative state; not signature verification."""
        from django.db import connections, router
        from django.db.models import Count
        from rest_framework.exceptions import PermissionDenied
        from .models import CompletionEnvelopeAttempt
        from .services import authorize

        project = self.get_object()
        actor = User.objects.filter(
            pk=request.user.pk, is_active=True
        ).first()
        if actor is None:
            raise PermissionDenied("Active completion reviewer required.")

        # Visibility of a project does not itself confer approval rights.
        authorize(actor, project, approval=True)

        common = {
            "project_id": str(project.pk),
            "read_only": True,
            "provider_verified": False,
            "installation_complete_qualified": False,
            "completion_authorized": False,
            "retry_authorized": False,
        }

        approved = project.current_approved
        if (
            project.state == "CANCELLED"
            or approved is None
            or approved.status != "APPROVED"
            or approved.project_id != project.pk
        ):
            return Response({
                **common,
                "status": "PREREQUISITES_MISSING",
                "attempt_count": 0,
                "attempt_states": [],
                "reason": "An active project and current approved MSR are required.",
            })

        alias = router.db_for_read(CompletionEnvelopeAttempt)
        connection = connections[alias]
        with connection.cursor() as cursor:
            available = set(connection.introspection.table_names(cursor))

        if CompletionEnvelopeAttempt._meta.db_table not in available:
            return Response({
                **common,
                "status": "SCHEMA_UNAVAILABLE",
                "attempt_count": 0,
                "attempt_states": [],
                "reason": "Envelope attempt storage is unavailable.",
            })

        rows = list(
            CompletionEnvelopeAttempt.objects.using(alias).filter(
                release_package__plan__msr_id=approved.pk
            ).values("state").annotate(
                count=Count("pk")
            ).order_by("state")
        )

        known_states = {
            "AUTH_PENDING",
            "NETWORK_STARTED",
            "SENT_UNCHECKED",
            "SEND_UNCERTAIN",
            "CANCELLED_UNSENT",
        }

        states = [
            {
                "state": (
                    row["state"]
                    if row["state"] in known_states
                    else "UNKNOWN_UNVERIFIED"
                ),
                "count": row["count"],
            }
            for row in rows
        ]

        return Response({
            **common,
            "status": "ATTEMPTS_UNVERIFIED" if rows else "NO_ATTEMPTS",
            "attempt_count": sum(row["count"] for row in rows),
            "attempt_states": states,
            "reason": (
                "Recorded envelope attempts do not independently "
                "verify DocuSign signatures or authorize completion."
            ),
        })

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response

