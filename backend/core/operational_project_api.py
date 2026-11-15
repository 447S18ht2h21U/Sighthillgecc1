import os

from django.conf import settings
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from .models import Project, User
from .operational_visibility import operational_project_scope

def operational_sales_status_available():
    if not settings.DEBUG or os.environ.get("GECC_SALES_STATUS_ENABLED") != "1":
        return False

    required = {
        "core_project",
        "core_projectsalesstatuschange",
        "django_migrations",
    }

    if not required.issubset(set(connection.introspection.table_names())):
        return False

    with connection.cursor() as cursor:
        columns = {
            column.name
            for column in connection.introspection.get_table_description(
                cursor, "core_project"
            )
        }

    if "sales_status" not in columns:
        return False

    return MigrationRecorder.Migration.objects.using(
        connection.alias
    ).filter(
        app="core",
        name="0088_sales_status_audit_guard_5003",
    ).exists()


class OperationalProjectSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.legal_name', read_only=True)
    sales_status = serializers.SerializerMethodField()

    def get_sales_status(self, obj):
        if not hasattr(self, "_sales_status_available"):
            self._sales_status_available = operational_sales_status_available()

        return obj.sales_status if self._sales_status_available else None

    class Meta:
        model = Project
        fields = ['id', 'code', 'customer', 'customer_name', 'location', 'sales_associate', 'state', 'sales_status', 'created_at']
        read_only_fields = fields

class OperationalProjectPagination(PageNumberPagination):
    page_size = 50

class OperationalProjectViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OperationalProjectSerializer
    pagination_class = OperationalProjectPagination
    http_method_names = ['get', 'post', 'head', 'options']
    queryset = Project.objects.none()

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Project.objects.none()
        actor = User.objects.filter(pk=user.pk, is_active=True).first()
        if actor is None:
            return Project.objects.none()
        queryset = operational_project_scope(actor).select_related('customer')

        if not operational_sales_status_available():
            queryset = queryset.defer('sales_status')

        return queryset.order_by('-created_at', '-id')



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


    @action(
        detail=True,
        methods=["get"],
        url_path="draft-receipt-package",
    )
    def draft_receipt_package(self, request, pk=None):
        """Comptroller/CEO read-only draft retention status.

        Never issues a document, supplies PDF/ZIP bytes, or establishes
        receipt delivery, installation authorization, or completion.
        """
        from django.core.exceptions import ValidationError
        from django.db import connections, router
        from rest_framework.exceptions import PermissionDenied
        from .models import ReceiptDraftPackage, Role
        from .receipt_draft_retention_4803 import (
            verify_retained_draft_package,
        )

        project = self.get_object()
        actor = User.objects.filter(
            pk=request.user.pk, is_active=True
        ).first()

        if (
            actor is None
            or actor.role not in (Role.CEO, Role.COMPTROLLER)
        ):
            raise PermissionDenied(
                "CEO or Comptroller authorization required."
            )

        result = {
            "project_id": str(project.pk),
            "read_only": True,
            "status": "NO_DRAFT_PACKAGE",
            "storage_available": False,
            "draft_package_count": 0,
            "verified_draft_package_count": 0,
            "integrity_verified": False,
            "draft_only": True,
            "final_receipt_verified": False,
            "issuance_authorized": False,
            "provider_email_authenticated": False,
            "customer_delivery_verified": False,
            "completion_authorized": False,
        }

        msr = project.current_approved

        if (
            msr is None
            or msr.status != "APPROVED"
            or msr.project_id != project.pk
            or project.state == "CANCELLED"
        ):
            result["status"] = "PREREQUISITES_MISSING"
            return Response(result)

        alias = router.db_for_read(ReceiptDraftPackage)
        connection = connections[alias]

        with connection.cursor() as cursor:
            tables = set(connection.introspection.table_names(cursor))

        if ReceiptDraftPackage._meta.db_table not in tables:
            result["status"] = "SCHEMA_UNAVAILABLE"
            return Response(result)

        result["storage_available"] = True

        records = list(
            ReceiptDraftPackage.objects.using(alias).filter(
                project_id=project.pk,
                msr_id=msr.pk,
            ).order_by("created_at", "pk")
        )

        result["draft_package_count"] = len(records)

        if not records:
            return Response(result)

        for record in records:
            try:
                verified = verify_retained_draft_package(
                    project=project,
                    record=record,
                )
            except (ValidationError, ValueError, TypeError):
                result["status"] = "INTEGRITY_FAILED"
                result["integrity_verified"] = False
                result["verified_draft_package_count"] = 0
                return Response(result)

            if (
                verified.integrity_verified is not True
                or verified.status != "DRAFT_NOT_ISSUED"
                or verified.issuance_authorized is not False
                or verified.customer_delivery_verified is not False
                or verified.completion_authorized is not False
            ):
                result["status"] = "INTEGRITY_FAILED"
                result["integrity_verified"] = False
                result["verified_draft_package_count"] = 0
                return Response(result)

            result["verified_draft_package_count"] += 1

        result["integrity_verified"] = True
        result["status"] = "VERIFIED_DRAFT_RETAINED"

        return Response(result)

    @action(
        detail=True,
        methods=["get"],
        url_path="installation-evidence-status",
    )
    def installation_evidence_status(self, request, pk=None):
        """Restricted read-only installation and FINAL Receipt evidence status."""
        from django.db import connections, router
        from django.db.utils import DatabaseError
        from django.core.exceptions import ValidationError
        from rest_framework.exceptions import PermissionDenied
        from .models import (
            Role, ProjectEvidence, InstallationSchedule,
            ReceiptDraftPackage,
        )
        from .installation_completion_evidence_4815 import (
            assess_installation_completion_evidence,
        )
        from .final_receipt_release_preflight_4812 import (
            assess_final_receipt_release_preflight,
        )

        actor = User.objects.filter(
            pk=getattr(request.user, "pk", None),
            is_active=True,
        ).first()
        if actor is None or actor.role not in (Role.CEO, Role.COMPTROLLER):
            raise PermissionDenied(
                "CEO or Comptroller evidence-review access required."
            )

        # Existing project scoping remains mandatory even for reviewers.
        project = self.get_object()

        result = {
            "project_id": str(project.pk),
            "read_only": True,
            "status": "PREREQUISITES_MISSING",
            "installation_schedule_completed": False,
            "physical_unit_count": 0,
            "verified_inspection_candidate_count": 0,
            "internal_acceptance_candidate_verified": False,
            "installation_source_integrity_verified": False,
            "installation_provenance_status": "UNVERIFIED",
            "installation_source_authenticated": False,
            "trusted_installation_evidence": False,
            "final_receipt_issuance_authorized": False,
            "provider_email_authenticated": False,
            "customer_delivery_verified": False,
            "completion_authorized": False,
            "blockers": [],
        }

        msr = project.current_approved
        if (
            project.state == "CANCELLED"
            or msr is None
            or msr.status != "APPROVED"
            or msr.project_id != project.pk
            or project.current_approved_id != msr.pk
        ):
            result["blockers"] = [
                "Active project with current approved MSR required."
            ]
            return Response(result)

        alias = router.db_for_read(ProjectEvidence)
        connection = connections[alias]
        required = (
            ProjectEvidence,
            InstallationSchedule,
            ReceiptDraftPackage,
        )

        try:
            with connection.cursor() as cursor:
                tables = set(connection.introspection.table_names(cursor))
        except DatabaseError:
            tables = set()

        if any(model._meta.db_table not in tables for model in required):
            result["status"] = "SCHEMA_UNAVAILABLE"
            result["blockers"] = [
                "Required installation evidence storage is unavailable."
            ]
            return Response(result)

        try:
            installation = assess_installation_completion_evidence(project)
            receipt = assess_final_receipt_release_preflight(project)

            if (
                installation.project_id != str(project.pk)
                or receipt.project_id != str(project.pk)
                or receipt.msr_id != str(msr.pk)
                or installation.trusted_installation_evidence is not False
                or installation.final_receipt_issuance_authorized is not False
                or installation.completion_authorized is not False
                or receipt.trusted_installation_evidence is not False
                or receipt.final_receipt_issuance_authorized is not False
                or receipt.final_receipt_verified is not False
                or receipt.provider_email_authenticated is not False
                or receipt.customer_delivery_verified is not False
                or receipt.completion_authorized is not False
                or installation.installation_provenance_status
                    != receipt.installation_provenance_status
                or installation.installation_source_integrity_verified
                    is not receipt.installation_source_integrity_verified
                or installation.acceptance_candidate_verified
                    is not receipt.acceptance_candidate_verified
            ):
                raise ValueError("Evidence authority or identity mismatch.")

            result.update({
                "status": "EVIDENCE_REVIEW_RELEASE_BLOCKED",
                "installation_schedule_completed": (
                    installation.operational_schedule_completed is True
                ),
                "physical_unit_count": installation.physical_unit_count,
                "verified_inspection_candidate_count": (
                    installation.verified_inspection_candidate_count
                ),
                "internal_acceptance_candidate_verified": (
                    installation.acceptance_candidate_verified is True
                ),
                "installation_source_integrity_verified": (
                    installation.installation_source_integrity_verified is True
                ),
                "installation_provenance_status": (
                    installation.installation_provenance_status
                ),
                "blockers": list(dict.fromkeys(
                    (*installation.blockers, *receipt.blockers)
                )),
            })
        except (ValueError, TypeError, AttributeError,
                ValidationError, DatabaseError):
            result["status"] = "EVIDENCE_VERIFICATION_FAILED"
            result["blockers"] = [
                "Independent evidence verification failed or is unavailable."
            ]

        return Response(result)

    @action(
        detail=True,
        methods=["get"],
        url_path="installation-inspection-review-queue",
    )
    def installation_inspection_review_queue(self, request, pk=None):
        """Comptroller-only read of an inspection awaiting independent review."""
        from django.db import connections, router
        from django.utils import timezone
        from .documents import canonical_hash
        from django.db.utils import DatabaseError
        from rest_framework.exceptions import PermissionDenied
        from .models import (
            Role, ProjectEvidence, InstallationSchedule,
        )
        from .post_installation_acceptance_4819 import (
            INSPECTION_KIND, REVIEW_KIND,
            _completed_schedule, _check_inspection,
        )

        actor = User.objects.filter(
            pk=getattr(request.user, "pk", None),
            is_active=True,
        ).first()
        if actor is None or actor.role != Role.COMPTROLLER:
            raise PermissionDenied(
                "Active Comptroller independent-review authority required."
            )

        project = self.get_object()
        result = {
            "project_id": str(project.pk),
            "read_only": True,
            "status": "PREREQUISITES_MISSING",
            "pending_inspection_id": None,
            "inspection_passed": None,
            "independent_review_recorded": False,
            "review_decision": None,
            "trusted_installation_evidence": False,
            "final_receipt_issuance_authorized": False,
            "customer_delivery_verified": False,
            "completion_authorized": False,
        }

        msr = project.current_approved
        if (
            project.state == "CANCELLED"
            or msr is None
            or msr.status != "APPROVED"
            or msr.project_id != project.pk
            or project.current_approved_id != msr.pk
        ):
            return Response(result)

        alias = router.db_for_read(ProjectEvidence)
        connection = connections[alias]
        try:
            with connection.cursor() as cursor:
                tables = set(connection.introspection.table_names(cursor))
        except DatabaseError:
            tables = set()

        if not {
            ProjectEvidence._meta.db_table,
            InstallationSchedule._meta.db_table,
        }.issubset(tables):
            result["status"] = "STORAGE_UNAVAILABLE"
            return Response(result)

        inspections = list(ProjectEvidence.objects.filter(
            msr=msr,
            kind=INSPECTION_KIND,
        ).order_by("pk"))

        reviews = list(ProjectEvidence.objects.filter(
            msr=msr,
            kind=REVIEW_KIND,
        ).order_by("pk"))

        if not inspections:
            result["status"] = "NO_INSPECTION"
            return Response(result)

        if len(inspections) != 1 or len(reviews) > 1:
            result["status"] = "INSPECTION_UNVERIFIED"
            return Response(result)

        inspection = inspections[0]

        try:
            schedule = _completed_schedule(project)
            checked = _check_inspection(
                inspection, project, msr, schedule
            )
            if (
                inspection.created_by_id
                    != schedule.installation_manager_id
                or inspection.created_at > timezone.now()
            ):
                raise ValueError("Inspector or chronology mismatch.")
        except Exception:
            result["status"] = "INSPECTION_UNVERIFIED"
            return Response(result)

        result["inspection_passed"] = checked["inspection_passed"]
        result["inspection_notes"] = checked["notes"]
        result["inspection_recorded_at"] = inspection.created_at.isoformat()
        result["independent_review_recorded"] = bool(reviews)

        if reviews:
            review = reviews[0]
            data = review.data
            valid = (
                type(data) is dict
                and review.digest == canonical_hash(data)
                and review.msr_id == msr.pk
                and review.kind == REVIEW_KIND
                and data.get("purpose") == REVIEW_KIND
                and data.get("status") in (
                    "REJECTED", "CANDIDATE_ACCEPTED"
                )
                and data.get("inspection_id") == str(inspection.pk)
                and data.get("inspection_digest") == inspection.digest
                and data.get("project_id") == str(project.pk)
                and data.get("msr_id") == str(msr.pk)
                and data.get("msr_version") == msr.number
                and data.get("snapshot_sha256")
                    == canonical_hash(msr.snapshot)
                and data.get("schedule_id") == str(schedule.pk)
                and data.get("inspector_id")
                    == str(inspection.created_by_id)
                and data.get("reviewer_id")
                    == str(review.created_by_id)
                and review.created_by_id != inspection.created_by_id
                and User.objects.filter(
                    pk=review.created_by_id,
                    is_active=True,
                    role=Role.COMPTROLLER,
                ).exists()
                and type(data.get("independently_examined")) is bool
                and type(data.get("reason")) is str
                and 15 <= len(data["reason"].strip()) <= 2000
                and data.get("trusted_installation_evidence") is False
                and data.get("final_receipt_issuance_authorized") is False
                and review.created_at >= inspection.created_at
                and review.created_at <= timezone.now()
            )
            if valid and data["status"] == "CANDIDATE_ACCEPTED":
                valid = (
                    checked["inspection_passed"] is True
                    and data["independently_examined"] is True
                )
            if not valid:
                result["status"] = "INSPECTION_UNVERIFIED"
                result["independent_review_recorded"] = False
                return Response(result)

            result["review_decision"] = (
                "REJECTED" if data["status"] == "REJECTED"
                else "INTERNAL_CANDIDATE_ACCEPTED"
            )
            # Internal decision verified; source authentication is not.
            result["status"] = "REVIEW_RECORDED_UNVERIFIED"
            return Response(result)

        result["pending_inspection_id"] = str(inspection.pk)
        result["status"] = "PENDING_INDEPENDENT_REVIEW"
        return Response(result)

    def _installation_entry_guard(self, request, role):
        """Fail closed outside the designated disposable browser database."""
        import os
        from pathlib import Path
        from django.conf import settings
        from rest_framework.exceptions import PermissionDenied
        from .models import Role

        actor = User.objects.filter(
            pk=getattr(request.user, "pk", None),
            is_active=True,
        ).first()

        if actor is None or actor.role != role:
            raise PermissionDenied("Authorized active role required.")

        if (
            settings.ENVIRONMENT != "development"
            or settings.DEBUG is not True
            or settings.DATABASES["default"]["ENGINE"]
                != "django.db.backends.sqlite3"
            or os.environ.get(
                "GECC_INSTALLATION_EVIDENCE_BROWSER_ENABLED"
            ) != "1"
        ):
            raise PermissionDenied(
                "Installation evidence entry is not enabled."
            )

        name = str(settings.DATABASES["default"]["NAME"])
        root = Path(settings.BASE_DIR).resolve().parent
        expected = (
            root / "recovery" / "1907P-4834"
            / "browser-acceptance.sqlite3"
        ).resolve()

        # Django's test runner converts :memory: into this exact
        # shared-cache SQLite memory URI for the default test alias.
        # Reject disk-backed SQLite and all other URI forms.
        test_memory_names = (
            ":memory:",
            "file:memorydb_default?mode=memory&cache=shared",
        )
        isolated_test = (
            name in test_memory_names
            and os.environ.get("GECC_SQLITE_PATH") == ":memory:"
            and all(
                os.environ.get(
                    f"VERIDIAN_{number}_TEST_INSTALL"
                ) == "ISOLATED_SQLITE_MEMORY"
                for number in (
                    "0071", "0072", "0073", "0074",
                    "0075", "0076", "0080"
                )
            )
        )

        isolated_browser = (
            name != ":memory:"
            and Path(name).resolve() == expected
            and expected.is_file()
        )

        if not (isolated_test or isolated_browser):
            raise PermissionDenied(
                "Only the protected isolated browser database is eligible."
            )

        return actor

    @action(
        detail=True,
        methods=["get"],
        url_path="equipment-unit-inventory",
    )
    def equipment_unit_inventory(self, request, pk=None):
        """Read-only approved physical-unit inventory; no capture authority."""
        from rest_framework.exceptions import PermissionDenied
        from .models import Role
        from .equipment_physical_units import physical_units_from_snapshot

        actor = User.objects.filter(
            pk=getattr(request.user, "pk", None),
            is_active=True,
        ).first()
        if actor is None or actor.role not in (
            Role.INSTALLATION_MANAGER,
            Role.COMPTROLLER,
            Role.CEO,
        ):
            raise PermissionDenied(
                "Authorized equipment inventory viewer required."
            )

        # get_object() also applies operational project visibility.
        project = self.get_object()
        result = {
            "project_id": str(project.pk),
            "msr_id": None,
            "status": "INVENTORY_UNAVAILABLE",
            "units": [],
            "read_only": True,
            "physical_inspection_verified": False,
            "trusted_installation_evidence": False,
            "installation_authorized": False,
            "final_receipt_issuance_authorized": False,
            "completion_authorized": False,
        }

        msr = project.current_approved
        if (
            project.state == "CANCELLED"
            or msr is None
            or msr.status != "APPROVED"
            or msr.project_id != project.pk
            or project.current_approved_id != msr.pk
        ):
            return Response(result)

        result["msr_id"] = str(msr.pk)

        try:
            units = physical_units_from_snapshot(
                msr_id=str(msr.pk),
                snapshot=msr.snapshot,
            )
        except (ValueError, TypeError, AttributeError):
            return Response(result)

        if not units:
            return Response(result)

        result["units"] = [
            {
                "unit_id": unit.unit_id,
                "row_number": unit.row_number,
                "unit_number": unit.unit_number,
                "brand": unit.brand,
                "residential_system_type": unit.residential_system_type,
                "model_number": unit.model_number,
                "description": unit.description,
                "category_of_work": unit.category_of_work,
            }
            for unit in units
        ]
        result["status"] = "APPROVED_UNIT_LIST_AVAILABLE"
        return Response(result)

    def _equipment_unit_review_read_guard(self, request):
        """Restricted read-only Comptroller equipment review queue."""
        import os
        from pathlib import Path
        from django.conf import settings
        from rest_framework.exceptions import PermissionDenied
        from .models import Role

        try:
            return self._installation_entry_guard(
                request, Role.COMPTROLLER
            )
        except PermissionDenied:
            request_user = getattr(request, "user", None)
            if request_user is None:
                raise

            actor = User.objects.filter(
                pk=getattr(request_user, "pk", None),
                is_active=True,
            ).first()

            expected = (
                Path(settings.BASE_DIR).resolve().parent
                / "recovery"
                / "browser-acceptance-5050"
                / "acceptance.sqlite3"
            ).resolve()

            db_name = str(settings.DATABASES["default"]["NAME"])
            configured = os.environ.get("GECC_SQLITE_PATH", "")

            allowed = (
                actor is not None
                and actor.role == Role.COMPTROLLER
                and settings.ENVIRONMENT == "development"
                and settings.DEBUG is True
                and settings.DATABASES["default"]["ENGINE"]
                    == "django.db.backends.sqlite3"
                and db_name not in ("", ":memory:")
                and Path(db_name).resolve() == expected
                and bool(configured)
                and Path(configured).resolve() == expected
                and expected.is_file()
            )

            if not allowed:
                raise

            return actor

    @action(
        detail=True,
        methods=["get"],
        url_path="equipment-unit-review-queue",
    )
    def equipment_unit_review_queue(self, request, pk=None):
        """Read-only physical-unit queue; no decision or trust promotion."""
        from .models import Role, ProjectEvidence
        from .documents import canonical_hash
        from .equipment_physical_units import physical_units_from_snapshot
        from .equipment_physical_capture_pending_service import (
            KIND as PENDING_KIND,
        )
        from .equipment_physical_inspection_review_service import (
            REVIEW_KIND,
        )

        self._equipment_unit_review_read_guard(request)
        project = self.get_object()
        result = {
            "project_id": str(project.pk),
            "msr_id": None,
            "status": "INVENTORY_UNAVAILABLE",
            "units": [],
            "read_only": True,
            "source_authenticated": False,
            "trusted_installation_evidence": False,
            "installation_authorized": False,
            "final_receipt_issuance_authorized": False,
            "customer_delivery_verified": False,
            "completion_authorized": False,
        }

        msr = project.current_approved
        if (
            project.state == "CANCELLED"
            or msr is None
            or msr.status != "APPROVED"
            or msr.project_id != project.pk
            or project.current_approved_id != msr.pk
        ):
            return Response(result)

        result["msr_id"] = str(msr.pk)
        try:
            units = physical_units_from_snapshot(
                msr_id=str(msr.pk), snapshot=msr.snapshot
            )
        except (ValueError, TypeError, AttributeError):
            return Response(result)

        if not units:
            return Response(result)

        pending_records = list(ProjectEvidence.objects.filter(
            msr=msr, kind=PENDING_KIND,
        ))
        review_records = list(ProjectEvidence.objects.filter(
            msr=msr, kind=REVIEW_KIND,
        ))
        snapshot_hash = canonical_hash(msr.snapshot)
        result["status"] = "QUEUE_AVAILABLE"

        for unit in units:
            entry = {
                "unit_id": unit.unit_id,
                "brand": unit.brand,
                "model_number": unit.model_number,
                "status": "NO_INSPECTION",
                "pending_id": None,
                "serial_number": None,
                "inspection_notes": None,
                "captured_at": None,
            }

            if any(type(item.data) is not dict for item in pending_records):
                entry["status"] = "EVIDENCE_INVALID"
                result["units"].append(entry)
                continue
            if any(type(item.data) is not dict for item in review_records):
                entry["status"] = "EVIDENCE_INVALID"
                result["units"].append(entry)
                continue

            matched = [
                item for item in pending_records
                if item.data.get("unit_id") == unit.unit_id
            ]
            if not matched:
                result["units"].append(entry)
                continue
            if len(matched) != 1:
                entry["status"] = "EVIDENCE_INVALID"
                result["units"].append(entry)
                continue

            pending = matched[0]
            data = pending.data
            valid = (
                pending.digest == canonical_hash(data)
                and data.get("purpose")
                    == "PHYSICAL_INSPECTION_PENDING_VERIFICATION"
                and data.get("project_id") == str(project.pk)
                and data.get("msr_id") == str(msr.pk)
                and data.get("msr_version") == msr.number
                and data.get("snapshot_sha256") == snapshot_hash
                and data.get("unit_id") == unit.unit_id
                and data.get("recorded_by")
                    == str(pending.created_by_id)
                and data.get("confirmed_in_person") is True
                and data.get("independently_verified") is False
                and data.get("trusted_installation_evidence") is False
                and data.get("installation_authorized") is False
                and type(data.get("serial_number")) is str
                and bool(data["serial_number"].strip())
                and type(data.get("inspection_notes")) is str
                and 15 <= len(data["inspection_notes"].strip()) <= 2000
                and type(data.get("captured_at")) is str
                and bool(data["captured_at"].strip())
            )

            decisions = [
                item for item in review_records
                if (
                    item.data.get("pending_id") == str(pending.pk)
                    or item.data.get("unit_id") == unit.unit_id
                )
            ]

            if not valid or len(decisions) > 1:
                entry["status"] = "EVIDENCE_INVALID"
            elif decisions:
                # A retained review is not proof of an accepted decision.
                entry["status"] = "REVIEW_RECORDED_UNVERIFIED"
            else:
                entry.update({
                    "status": "PENDING_INDEPENDENT_REVIEW",
                    "pending_id": str(pending.pk),
                    "serial_number": data["serial_number"],
                    "inspection_notes": data["inspection_notes"],
                    "captured_at": data["captured_at"],
                })

            result["units"].append(entry)

        return Response(result)

    @action(
        detail=True,
        methods=["post"],
        url_path="review-equipment-unit-inspection",
    )
    def review_equipment_unit_inspection(self, request, pk=None):
        """Comptroller-only independent review of a pending physical unit."""
        from uuid import UUID
        from django.db import transaction
        from rest_framework.exceptions import ValidationError
        from .documents import canonical_hash
        from .models import Role, ProjectEvidence
        from .equipment_physical_capture_pending_service import (
            KIND as PENDING_KIND,
        )
        from .equipment_physical_inspection_review_service import (
            REVIEW_KIND,
            review_pending_physical_inspection,
        )

        actor = self._installation_entry_guard(request, Role.COMPTROLLER)
        project = self.get_object()
        payload = request.data
        required = {
            "pending_id", "accept_candidate",
            "review_reason", "independently_examined",
        }
        if (
            not isinstance(payload, dict)
            or set(payload) != required
            or type(payload["pending_id"]) is not str
            or type(payload["accept_candidate"]) is not bool
            or type(payload["review_reason"]) is not str
            or type(payload["independently_examined"]) is not bool
            or not 15 <= len(payload["review_reason"].strip()) <= 2000
        ):
            raise ValidationError(
                "Explicit pending evidence, independent decision "
                "and written review reason required."
            )

        try:
            pending_id = str(UUID(payload["pending_id"]))
        except (ValueError, TypeError, AttributeError):
            raise ValidationError("Valid pending inspection identifier required.") from None

        if (
            payload["accept_candidate"]
            and payload["independently_examined"] is not True
        ):
            raise ValidationError(
                "Acceptance requires explicit independent examination."
            )

        with transaction.atomic():
            msr = project.current_approved
            if (
                project.state == "CANCELLED"
                or msr is None
                or msr.status != "APPROVED"
                or msr.project_id != project.pk
                or project.current_approved_id != msr.pk
            ):
                raise ValidationError("Current approved MSR required.")

            pending = ProjectEvidence.objects.select_for_update().filter(
                pk=pending_id, msr=msr, kind=PENDING_KIND,
            ).first()
            if pending is None:
                raise ValidationError(
                    "Pending inspection must belong to the selected project."
                )

            data = pending.data
            if (
                type(data) is not dict
                or pending.digest != canonical_hash(data)
                or data.get("purpose")
                    != "PHYSICAL_INSPECTION_PENDING_VERIFICATION"
                or data.get("project_id") != str(project.pk)
                or data.get("msr_id") != str(msr.pk)
                or data.get("msr_version") != msr.number
                or data.get("snapshot_sha256") != canonical_hash(msr.snapshot)
                or data.get("recorded_by") != str(pending.created_by_id)
                or data.get("confirmed_in_person") is not True
                or data.get("independently_verified") is not False
                or data.get("trusted_installation_evidence") is not False
                or data.get("installation_authorized") is not False
                or type(data.get("unit_id")) is not str
                or not data["unit_id"].strip()
            ):
                raise ValidationError("Pending inspection integrity failed.")

            if pending.created_by_id == actor.pk:
                raise ValidationError("No self-review permitted.")

            if ProjectEvidence.objects.filter(
                msr=msr, kind=REVIEW_KIND,
                data__pending_id=str(pending.pk),
            ).exists():
                raise ValidationError(
                    "An independent decision already exists for this inspection."
                )

            decision = review_pending_physical_inspection(
                actor=actor,
                pending_id=pending.pk,
                accept_candidate=payload["accept_candidate"],
                review_reason=payload["review_reason"],
                independently_examined=payload["independently_examined"],
            )

        return Response({
            "project_id": str(project.pk),
            "msr_id": str(msr.pk),
            "pending_id": str(pending.pk),
            "review_id": str(decision.pk),
            "status": (
                "INTERNAL_CANDIDATE_ACCEPTED"
                if payload["accept_candidate"] else "REJECTED"
            ),
            "source_authenticated": False,
            "trusted_installation_evidence": False,
            "installation_authorized": False,
            "final_receipt_issuance_authorized": False,
            "customer_delivery_verified": False,
            "completion_authorized": False,
        }, status=201)

    @action(
        detail=True,
        methods=["post"],
        url_path="record-equipment-unit-inspection",
    )
    def record_equipment_unit_inspection(self, request, pk=None):
        """Record a development-only pending physical-unit observation."""
        from datetime import datetime
        from django.db import transaction
        from django.utils import timezone
        from rest_framework.exceptions import ValidationError
        from .models import Role, InstallationSchedule
        from .equipment_physical_capture_pending_service import (
            record_pending_physical_inspection,
        )

        actor = self._installation_entry_guard(
            request, Role.INSTALLATION_MANAGER
        )
        project = self.get_object()
        payload = request.data

        required = {
            "msr_id", "unit_id", "serial_number",
            "captured_at", "installation_starts_at",
            "confirmed_in_person", "inspection_notes",
        }
        if (
            not isinstance(payload, dict)
            or set(payload) != required
            or any(
                type(payload[key]) is not str
                for key in required - {"confirmed_in_person"}
            )
            or payload["confirmed_in_person"] is not True
        ):
            raise ValidationError(
                "Explicit equipment identification and in-person "
                "inspection attestation required."
            )

        if (
            not payload["msr_id"].strip()
            or not payload["unit_id"].strip()
            or not payload["serial_number"].strip()
            or not 15 <= len(payload["inspection_notes"].strip()) <= 2000
        ):
            raise ValidationError(
                "Approved equipment, serial number and specific notes required."
            )

        try:
            captured_at = datetime.fromisoformat(
                payload["captured_at"].replace("Z", "+00:00")
            )
            starts_at = datetime.fromisoformat(
                payload["installation_starts_at"].replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            raise ValidationError(
                "Valid explicitly entered inspection timestamps required."
            ) from None

        if (
            timezone.is_naive(captured_at)
            or timezone.is_naive(starts_at)
            or captured_at > timezone.now()
            or captured_at > starts_at
        ):
            raise ValidationError(
                "Inspection times must be timezone-aware, chronological "
                "and must not claim a future observation."
            )

        with transaction.atomic():
            schedules = list(
                InstallationSchedule.objects.select_for_update().filter(
                    project=project,
                    status__in=(
                        InstallationSchedule.Status.SCHEDULED,
                        InstallationSchedule.Status.COMPLETED,
                    ),
                )
            )
            if (
                len(schedules) != 1
                or schedules[0].installation_manager_id != actor.pk
                or schedules[0].cancelled_at is not None
                or schedules[0].scheduled_date is None
                or timezone.localtime(starts_at).date()
                    != schedules[0].scheduled_date
            ):
                raise ValidationError(
                    "Exactly one eligible schedule assigned to the "
                    "recording Installation Manager is required, and "
                    "the stated installation start must match its date."
                )

            msr = project.current_approved
            if (
                project.state == "CANCELLED"
                or msr is None
                or msr.status != "APPROVED"
                or msr.project_id != project.pk
                or project.current_approved_id != msr.pk
                or str(msr.pk) != payload["msr_id"]
            ):
                raise ValidationError(
                    "The selected current approved MSR is required."
                )

            record = record_pending_physical_inspection(
                actor=actor,
                project_id=project.pk,
                msr_id=str(msr.pk),
                unit_id=payload["unit_id"],
                serial_number=payload["serial_number"],
                captured_at=captured_at,
                installation_starts_at=starts_at,
                confirmed_in_person=True,
                inspection_notes=payload["inspection_notes"],
            )

        return Response({
            "project_id": str(project.pk),
            "msr_id": str(msr.pk),
            "unit_id": payload["unit_id"],
            "evidence_id": str(record.pk),
            "status": "PENDING_INDEPENDENT_REVIEW",
            "source_authenticated": False,
            "trusted_installation_evidence": False,
            "installation_authorized": False,
            "final_receipt_issuance_authorized": False,
            "customer_delivery_verified": False,
            "completion_authorized": False,
        }, status=201)

    @action(
        detail=True,
        methods=["post"],
        url_path="record-installation-inspection",
    )
    def record_installation_inspection(self, request, pk=None):
        """Assigned Installation Manager records an immutable candidate."""
        from .models import Role
        from rest_framework.exceptions import ValidationError
        from .post_installation_acceptance_4819 import (
            record_post_installation_inspection,
        )

        actor = self._installation_entry_guard(
            request, Role.INSTALLATION_MANAGER
        )
        project = self.get_object()
        payload = request.data

        if (
            not isinstance(payload, dict)
            or set(payload) != {"inspection_passed", "notes"}
            or type(payload["inspection_passed"]) is not bool
            or type(payload["notes"]) is not str
        ):
            raise ValidationError(
                "Explicit inspection outcome and notes required."
            )

        record = record_post_installation_inspection(
            actor=actor,
            project_id=project.pk,
            inspection_passed=payload["inspection_passed"],
            notes=payload["notes"],
        )

        return Response({
            "project_id": str(project.pk),
            "inspection_id": str(record.pk),
            "status": "INSPECTION_CANDIDATE_RECORDED",
            "read_only": False,
            "source_authenticated": False,
            "trusted_installation_evidence": False,
            "final_receipt_issuance_authorized": False,
            "customer_delivery_verified": False,
            "completion_authorized": False,
        }, status=201)

    @action(
        detail=True,
        methods=["post"],
        url_path="review-installation-inspection",
    )
    def review_installation_inspection(self, request, pk=None):
        """Different active Comptroller reviews the recorded candidate."""
        from .models import Role, ProjectEvidence
        from .post_installation_acceptance_4819 import (
            INSPECTION_KIND,
            review_post_installation_inspection,
        )
        from rest_framework.exceptions import ValidationError

        actor = self._installation_entry_guard(
            request, Role.COMPTROLLER
        )
        project = self.get_object()
        payload = request.data

        if (
            not isinstance(payload, dict)
            or set(payload) != {
                "inspection_id", "accept", "reason",
                "independently_examined"
            }
            or type(payload["inspection_id"]) is not str
            or type(payload["accept"]) is not bool
            or type(payload["reason"]) is not str
            or type(payload["independently_examined"]) is not bool
        ):
            raise ValidationError(
                "Explicit inspection review fields required."
            )

        msr = project.current_approved
        if (
            msr is None
            or not ProjectEvidence.objects.filter(
                pk=payload["inspection_id"],
                msr=msr,
                kind=INSPECTION_KIND,
            ).exists()
        ):
            raise ValidationError(
                "Inspection must belong to the selected approved project."
            )

        record = review_post_installation_inspection(
            actor=actor,
            inspection_id=payload["inspection_id"],
            accept=payload["accept"],
            reason=payload["reason"],
            independently_examined=payload["independently_examined"],
        )

        return Response({
            "project_id": str(project.pk),
            "review_id": str(record.pk),
            "status": (
                "INTERNAL_CANDIDATE_ACCEPTED"
                if payload["accept"]
                else "INSPECTION_CANDIDATE_REJECTED"
            ),
            "source_authenticated": False,
            "trusted_installation_evidence": False,
            "final_receipt_issuance_authorized": False,
            "customer_delivery_verified": False,
            "completion_authorized": False,
        }, status=201)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response

