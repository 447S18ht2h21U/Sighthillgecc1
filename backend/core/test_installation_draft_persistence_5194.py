import os
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.models import (
    AuditEvent,
    AuditHead,
    Customer,
    MSR,
    Project,
    ProjectEvidence,
    Role,
    User,
)
from core import installation_draft_authorization_5179 as service
from core.installation_provider_oauth_4979 import canonical_hash


FLAG = "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED"


def disposable_customer_fields(*, created_by):
    """Populate required primitive fields using the real Customer model."""
    from django.db import models

    result = {}

    for field in Customer._meta.concrete_fields:
        if (
            field.primary_key
            or field.auto_created
            or field.has_default()
            or field.null
            or getattr(field, "auto_now", False)
            or getattr(field, "auto_now_add", False)
        ):
            continue

        if isinstance(field, models.ForeignKey):
            if field.name == "created_by":
                result[field.name] = created_by
                continue

            raise AssertionError(
                "Customer fixture has an unexpected required relation: "
                + field.name
            )

        if isinstance(field, (models.CharField, models.TextField)):
            value = "5194 fixture " + field.name
            if isinstance(field, models.EmailField):
                value = "inspection5194@example.invalid"
            if field.max_length:
                value = value[:field.max_length]
            result[field.name] = value

        elif isinstance(field, models.BooleanField):
            result[field.name] = False

        elif isinstance(field, models.IntegerField):
            result[field.name] = 1

        elif isinstance(field, models.DecimalField):
            result[field.name] = 1

        elif isinstance(field, models.DateField):
            from datetime import date
            result[field.name] = date(2026, 11, 16)

        elif isinstance(field, models.JSONField):
            result[field.name] = {}

        else:
            raise AssertionError(
                "Unsupported required Customer fixture field: "
                + field.name
            )

    return result


@override_settings(ENVIRONMENT="development", DEBUG=True)
class DurableInspectionAuthorization5194Tests(TestCase):

    def setUp(self):
        self.flag = patch.dict(os.environ, {FLAG: "1"})
        self.flag.start()
        self.addCleanup(self.flag.stop)

        self.ceo = User.objects.create_user(
            username="inspection_5194_ceo",
            role=Role.CEO,
            initials="IC",
        )
        self.sales = User.objects.create_user(
            username="inspection_5194_sales",
            role=Role.SALES_ASSOCIATE,
            initials="IS",
        )

        self.customer = Customer.objects.create(
            **disposable_customer_fields(created_by=self.ceo)
        )

        self.project = Project.objects.create(
            code="INSPECTION-5194",
            customer=self.customer,
            location="Disposable acceptance fixture",
            sales_associate=self.sales,
            reviewer=self.ceo,
            state="DRAFT",
        )

        self.msr = MSR.objects.create(
            project=self.project,
            number=1,
            status="APPROVED",
            snapshot={},
            created_by=self.sales,
            prepared_by=self.sales,
            approved_by=self.ceo,
        )

        self.project.current_approved = self.msr
        self.project.save(update_fields=["current_approved"])

        self.envelope = SimpleNamespace(
            project_id=str(self.project.pk),
            approved_msr_id=str(self.msr.pk),
            approved_msr_version="1",
        )

        self.fingerprint = patch.object(
            service, "_fingerprint", return_value="a" * 64
        )
        self.fingerprint.start()
        self.addCleanup(self.fingerprint.stop)

        AuditHead.objects.get_or_create(pk=1)

    def authorize(self):
        return service.record_draft_intent(
            actor=self.ceo,
            project_id=self.project.pk,
            envelope=self.envelope,
            confirmed=True,
        )

    def test_real_evidence_and_audit_are_persisted(self):
        before_events = AuditEvent.objects.count()

        result = self.authorize()

        evidence = ProjectEvidence.objects.get(
            pk=result["evidence_id"]
        )

        self.assertEqual(evidence.msr_id, self.msr.pk)
        self.assertEqual(evidence.created_by_id, self.ceo.pk)
        self.assertEqual(evidence.kind, service.KIND)
        self.assertEqual(
            evidence.digest,
            canonical_hash(evidence.data),
        )

        self.assertEqual(
            evidence.data["draft_payload_sha256"], "a" * 64
        )
        self.assertEqual(
            evidence.data["project_id"], str(self.project.pk)
        )
        self.assertEqual(
            evidence.data["msr_id"], str(self.msr.pk)
        )
        self.assertFalse(
            evidence.data["provider_request_authorized"]
        )
        self.assertFalse(evidence.data["send_authorized"])
        self.assertFalse(
            evidence.data["project_completion_authorized"]
        )

        self.assertEqual(
            AuditEvent.objects.count(), before_events + 1
        )

        event = AuditEvent.objects.latest("sequence")
        self.assertEqual(event.actor_id, self.ceo.pk)
        self.assertEqual(
            event.action,
            "installation.inspection_sandbox_draft_intent_recorded",
        )
        self.assertEqual(event.entity_id, self.project.pk)
        self.assertEqual(
            event.payload["evidence_id"], str(evidence.pk)
        )

    def test_duplicate_authorization_rejected_without_extra_audit(self):
        self.authorize()

        before_evidence = ProjectEvidence.objects.filter(
            msr=self.msr, kind=service.KIND
        ).count()
        before_audit = AuditEvent.objects.count()

        with self.assertRaises(ValidationError):
            self.authorize()

        self.assertEqual(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind=service.KIND
            ).count(),
            before_evidence,
        )
        self.assertEqual(
            AuditEvent.objects.count(),
            before_audit,
        )

    def test_other_project_package_rejected_without_database_write(self):
        self.envelope.project_id = (
            "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
        )

        before_audit = AuditEvent.objects.count()

        with self.assertRaises(ValidationError):
            self.authorize()

        self.assertFalse(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind=service.KIND
            ).exists()
        )
        self.assertEqual(
            AuditEvent.objects.count(), before_audit
        )