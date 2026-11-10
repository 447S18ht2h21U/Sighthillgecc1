"""Real database evidence integration for the unregistered installation preview."""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from .ceo_payment_exception_services import (
    request_payment_exception,
    decide_payment_exception,
    revoke_payment_exception,
    has_valid_payment_exception,
)
from .documents import canonical_hash
from .equipment_serial_capture_service import SERIAL_KIND, capture_synthetic_serial
from .installation_consolidated_preview import preview_consolidated_installation
from .models import (
    AuditEvent, CustomerPayment, CustomerSignatureEvidence,
    ProjectEvidence, Role, User,
)
from .payment_services import verify_customer_payment
from .customer_payment_bank_confirmation_services import (
    confirm_customer_payment_bank_availability,
)
from . import test_equipment_serial_exception_service as serial_fixture
from . import tests as foundation_fixture


@override_settings(DEBUG=True, ENVIRONMENT="development")
class RealTwoStageDatabaseRegressionTests(TestCase):
    # Reuse fixture helpers without inheriting their unrelated test methods.
    edit_submit = foundation_fixture.FoundationTests.edit_submit
    approve = foundation_fixture.FoundationTests.approve
    request = serial_fixture.SerialExceptionRequestServiceTests.request
    decide = serial_fixture.SerialExceptionRequestServiceTests.decide
    revoke = serial_fixture.SerialExceptionRequestServiceTests.revoke
    make_synthetic_approved_revision = (
        serial_fixture.SerialExceptionRequestServiceTests.make_synthetic_approved_revision
    )

    def setUp(self):
        foundation_fixture.FoundationTests.setUp(self)
        self.installation_manager = User.objects.create_user(
            username="combined_real_installation_manager",
            password="synthetic-test-only",
            role=Role.INSTALLATION_MANAGER,
            initials="IM",
        )

    def prepare(self, *, payment_option="50_PERCENT_DEPOSIT"):
        # Equipment and commercial terms are submitted BEFORE MSR approval.
        self.snapshot.update({
            "equipment": [{
                "brand": "Goodman",
                "residential_system_type": "Heat Pumps (R-32)",
                "model_number": "GZV9S",
                "description": "Synthetic integrated regression equipment",
                "quantity": 2,
                "category_of_work": "New installation",
            }],
            "financing_type": (
                "NON_FINANCED"
                if payment_option == "100_PERCENT_COMPLETION"
                else "FINANCED"
            ),
            "payment_option": payment_option,
            "payment_terms": (
                "100% due after completion."
                if payment_option == "100_PERCENT_COMPLETION"
                else "50% deposit; balance upon completion."
            ),
            "base_price": "10000.00",
            "discount": "0.00",
            "tax": "0.00",
            "total_price": "10000.00",
        })

        # STEP 1907P-4590: Synthetic active catalog selection.
        # Never bypass the real MSR catalog validation boundary.
        from .models import (
            ProductCatalogCollection,
            ProductCatalogMembership,
            EquipmentCatalogItem,
        )

        collection_fields = {
            field.name
            for field in ProductCatalogCollection._meta.concrete_fields
        }
        collection_values = {
            "created_by": self.manager,
        }
        if "name" in collection_fields:
            collection_values["name"] = "Synthetic regression catalog"
        elif "title" in collection_fields:
            collection_values["title"] = "Synthetic regression catalog"
        else:
            collection_values["label"] = "Synthetic regression catalog"
        if "code" in collection_fields:
            collection_values["code"] = "TEST-COMBINED-REAL"
        if "description" in collection_fields:
            collection_values["description"] = (
                "Disposable fixture equipment only"
            )
        if "is_active" in collection_fields:
            collection_values["is_active"] = True

        catalog = ProductCatalogCollection.objects.create(
            **collection_values
        )
        equipment_details = {
            key: self.snapshot["equipment"][0][key]
            for key in (
                "brand", "residential_system_type",
                "model_number", "description",
            )
        }
        catalog_item = EquipmentCatalogItem.objects.create(
            **equipment_details,
            created_by=self.manager,
            is_active=True,
        )
        ProductCatalogMembership.objects.create(
            catalog=catalog,
            equipment=catalog_item,
            created_by=self.manager,
        )

        self.snapshot["equipment"][0]["catalog_id"] = str(catalog.pk)
        self.snapshot["equipment"][0]["equipment_id"] = str(
            catalog_item.pk
        )

        approved = self.approve()
        self.project.refresh_from_db()
        self.assertEqual(self.project.current_approved_id, approved.pk)
        return approved

    def stage_one_evidence(
        self, msr, *, contract=True, cancellation=True,
        deposit=True, signed_days_ago=10,
        cancellation_days_after_signature=1,
    ):
        # Actual evidence services and records; no mocked stage-one result.
        signed_at = timezone.now() - timedelta(days=signed_days_ago)
        if contract:
            CustomerSignatureEvidence.objects.create(
                msr=msr,
                document_kind=CustomerSignatureEvidence.DocumentKind.CONTRACT,
                signer_role=CustomerSignatureEvidence.SignerRole.CUSTOMER,
                signer_name="Synthetic Customer",
                signer_email="synthetic@example.com",
                signed_at=signed_at,
                provider_reference="TEST-REAL-STAGE1-CONTRACT",
                digest="TEST-REAL-STAGE1-CONTRACT-DIGEST",
            )
        if cancellation:
            ProjectEvidence.objects.create(
                msr=msr,
                kind="CANCELLATION_DEADLINE",
                created_by=self.comptroller,
                data={
                    "verified": True,
                    "deadline": (
                        signed_at + timedelta(days=cancellation_days_after_signature)
                    ).isoformat(),
                },
                digest="TEST-REAL-STAGE1-CANCELLATION-DIGEST",
            )
        if deposit:
            payment = CustomerPayment.objects.create(
                project=self.project,
                msr=msr,
                kind=CustomerPayment.Kind.DEPOSIT,
                amount="5000.00",
                received_date=timezone.localdate(),
                payment_reference="TEST-REAL-STAGE1-DEPOSIT",
                status=CustomerPayment.Status.PENDING,
                recorded_by=self.comptroller,
            )
            verify_customer_payment(self.comptroller, payment.id)
            confirm_customer_payment_bank_availability(
                actor=self.comptroller,
                payment_id=payment.id,
                bank_reference="TEST-REAL-STAGE1-BANK",
                confirmation_date=timezone.localdate(),
                confirmation_method="Bank transaction reviewed",
                confirmation_note="Synthetic funds confirmed available.",
            )

    def serial(self, msr, unit, value):
        return capture_synthetic_serial(
            actor=self.installation_manager,
            project_id=self.project.pk,
            msr_id=msr.pk,
            unit_id=f"ROW-001-UNIT-{unit:03d}",
            serial_number=value,
        )

    def combined(self, **kwargs):
        values = {
            "project_id": self.project.pk,
            "installation_starts_at": timezone.now() + timedelta(hours=1),
            "now": timezone.now(),
        }
        values.update(kwargs)
        result = preview_consolidated_installation(**values)
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.scheduling_authorized)
        self.assertFalse(result.installation_authorized)
        return result

    def test_revised_msr_cannot_authorize_installation_start(self):
        from .installation_start_policy_preview import preview_installation_start

        msr = self.prepare()
        self.stage_one_evidence(msr)
        self.serial(msr, 1, "REVISION-START-A")
        self.serial(msr, 2, "REVISION-START-B")
        self.assertTrue(self.combined().combined_candidate)

        revised = self.make_synthetic_approved_revision(msr)
        self.assertNotEqual(revised.pk, msr.pk)

        assessment = self.combined()
        self.assertFalse(assessment.stage_one_candidate)
        self.assertFalse(assessment.stage_two_candidate)

        decision = preview_installation_start(
            schedule_status="SCHEDULED",
            stage_one_candidate=assessment.stage_one_candidate,
            stage_two_candidate=assessment.stage_two_candidate,
            trusted_equipment_evidence=assessment.trusted_installation_evidence,
        )
        self.assertFalse(decision.ready_to_start)
        self.assertFalse(decision.start_authorized)
        self.assertFalse(decision.installation_started)

    def test_wrong_project_identifier_cannot_authorize_start(self):
        from uuid import uuid4
        from .equipment_recorded_readiness_preview import preview_recorded_equipment
        from .installation_start_policy_preview import preview_installation_start

        msr = self.prepare()
        self.serial(msr, 1, "PROJECT-BOUND-A")
        self.serial(msr, 2, "PROJECT-BOUND-B")

        assessment = preview_recorded_equipment(
            project_id=uuid4(),
            msr_id=msr.pk,
            installation_starts_at=timezone.now() + timedelta(hours=1),
        )
        self.assertFalse(assessment.candidate_complete)
        self.assertFalse(assessment.trusted_installation_evidence)

        decision = preview_installation_start(
            schedule_status="SCHEDULED",
            stage_one_candidate=True,
            stage_two_candidate=assessment.candidate_complete,
            trusted_equipment_evidence=assessment.trusted_installation_evidence,
        )
        self.assertFalse(decision.ready_to_start)
        self.assertFalse(decision.start_authorized)
        self.assertFalse(decision.installation_started)
    def test_real_cross_project_serial_isolation(self):
        from rest_framework.exceptions import ValidationError
        from .models import Customer
        from .services import create_project
        from .equipment_recorded_readiness_preview import (
            preview_recorded_equipment,
        )
        from .installation_start_policy_preview import (
            preview_installation_start,
        )

        msr_a = self.prepare()
        self.serial(msr_a, 1, "PROJECT-A-UNIT-001")
        self.serial(msr_a, 2, "PROJECT-A-UNIT-002")

        starts_at = timezone.now() + timedelta(hours=1)
        ready_a = preview_recorded_equipment(
            project_id=self.project.pk,
            msr_id=msr_a.pk,
            installation_starts_at=starts_at,
        )
        self.assertTrue(ready_a.candidate_complete, ready_a.blockers)

        customer_b = Customer.objects.create(
            legal_name="Synthetic Project B Customer",
            billing_address="20 Test Street",
            created_by=self.other,
        )
        project_b = create_project(
            self.other,
            customer_b,
            "22 Test Street",
            self.other,
            self.manager,
        )
        self.assertNotEqual(project_b.pk, self.project.pk)

        evidence_before = ProjectEvidence.objects.count()

        with self.assertRaises(ValidationError):
            capture_synthetic_serial(
                actor=self.installation_manager,
                project_id=project_b.pk,
                msr_id=msr_a.pk,
                unit_id="ROW-001-UNIT-001",
                serial_number="FORGED-CROSS-PROJECT",
            )

        self.assertEqual(
            ProjectEvidence.objects.count(), evidence_before
        )

        ready_b = preview_recorded_equipment(
            project_id=project_b.pk,
            msr_id=msr_a.pk,
            installation_starts_at=starts_at,
        )
        self.assertFalse(ready_b.candidate_complete)
        self.assertFalse(ready_b.trusted_installation_evidence)
        self.assertFalse(ready_b.installation_authorized)

        decision = preview_installation_start(
            schedule_status="SCHEDULED",
            stage_one_candidate=True,
            stage_two_candidate=ready_b.candidate_complete,
            trusted_equipment_evidence=ready_b.trusted_installation_evidence,
        )
        self.assertFalse(decision.ready_to_start)
        self.assertFalse(decision.start_authorized)
        self.assertFalse(decision.installation_started)
    def test_full_installation_preview_preserves_records(self):
        from .installation_start_policy_preview import (
            preview_installation_start,
        )
        from .models import Project

        msr = self.prepare()
        self.stage_one_evidence(msr)
        self.serial(msr, 1, "READONLY-UNIT-A")
        self.serial(msr, 2, "READONLY-UNIT-B")

        def fingerprint(model):
            pk_field = model._meta.pk.attname
            rows = model.objects.values()
            return tuple(
                sorted(
                    (
                        str(row[pk_field]),
                        canonical_hash({
                            key: str(value)
                            for key, value in row.items()
                        }),
                    )
                    for row in rows
                )
            )

        models = (Project, AuditEvent, ProjectEvidence)
        before = tuple(fingerprint(model) for model in models)

        assessment = self.combined()
        self.assertTrue(
            assessment.combined_candidate,
            (
                assessment.stage_one_blockers,
                assessment.stage_two_blockers,
            ),
        )

        decision = preview_installation_start(
            schedule_status="SCHEDULED",
            stage_one_candidate=assessment.stage_one_candidate,
            stage_two_candidate=assessment.stage_two_candidate,
            trusted_equipment_evidence=assessment.trusted_installation_evidence,
        )

        after = tuple(fingerprint(model) for model in models)

        self.assertEqual(before, after)
        self.assertFalse(decision.ready_to_start)
        self.assertFalse(decision.start_authorized)
        self.assertFalse(decision.installation_started)
    def test_real_schedule_with_synthetic_equipment_denies_start(self):
        from .models import InstallationSchedule
        from .installation_start_policy_preview import (
            preview_installation_start,
        )

        msr = self.prepare()
        self.stage_one_evidence(msr)
        self.serial(msr, 1, "SCHEDULE-UNIT-A")
        self.serial(msr, 2, "SCHEDULE-UNIT-B")

        schedule = InstallationSchedule.objects.create(
            project=self.project,
            scheduled_date=timezone.localdate(),
            installation_manager=self.installation_manager,
            scheduled_by=self.installation_manager,
            status="SCHEDULED",
        )
        schedule_id = schedule.pk

        assessment = self.combined()
        self.assertTrue(
            assessment.combined_candidate,
            (
                assessment.stage_one_blockers,
                assessment.stage_two_blockers,
            ),
        )

        decision = preview_installation_start(
            schedule_status=schedule.status,
            stage_one_candidate=assessment.stage_one_candidate,
            stage_two_candidate=assessment.stage_two_candidate,
            trusted_equipment_evidence=assessment.trusted_installation_evidence,
        )

        schedule.refresh_from_db()
        self.assertEqual(schedule.pk, schedule_id)
        self.assertEqual(schedule.status, "SCHEDULED")
        self.assertFalse(decision.ready_to_start)
        self.assertFalse(decision.start_authorized)
        self.assertFalse(decision.installation_started)
    def assess_closed_real_schedule(self, status):
        from .models import InstallationSchedule
        from .installation_start_policy_preview import (
            preview_installation_start,
        )

        msr = self.prepare()
        self.stage_one_evidence(msr)
        self.serial(msr, 1, "CLOSED-SCHEDULE-A")
        self.serial(msr, 2, "CLOSED-SCHEDULE-B")

        schedule = InstallationSchedule.objects.create(
            project=self.project,
            scheduled_date=timezone.localdate(),
            installation_manager=self.installation_manager,
            scheduled_by=self.installation_manager,
            status=status,
        )

        assessment = self.combined()
        self.assertTrue(
            assessment.combined_candidate,
            (
                assessment.stage_one_blockers,
                assessment.stage_two_blockers,
            ),
        )

        decision = preview_installation_start(
            schedule_status=schedule.status,
            stage_one_candidate=assessment.stage_one_candidate,
            stage_two_candidate=assessment.stage_two_candidate,
            trusted_equipment_evidence=assessment.trusted_installation_evidence,
        )

        schedule.refresh_from_db()
        self.assertEqual(schedule.status, status)
        self.assertFalse(decision.schedule_exists)
        self.assertFalse(decision.ready_to_start)
        self.assertFalse(decision.start_authorized)
        self.assertFalse(decision.installation_started)
        self.assertIn(
            "An active scheduled installation is required.",
            decision.blockers,
        )

    def test_closed_real_schedule_denies_complete_evidence_cancelled(self):
        self.assess_closed_real_schedule("CANCELLED")

    def test_closed_real_schedule_denies_complete_evidence_completed(self):
        self.assess_closed_real_schedule("COMPLETED")
    def test_synthetic_equipment_cannot_authorize_start(self):
        from .equipment_recorded_readiness_preview import (
            preview_recorded_equipment,
        )
        from .installation_start_policy_preview import (
            preview_installation_start,
        )

        msr = self.prepare()
        self.serial(msr, 1, "SYNTHETIC-START-A")
        self.serial(msr, 2, "SYNTHETIC-START-B")

        equipment = preview_recorded_equipment(
            project_id=self.project.pk,
            msr_id=msr.pk,
            installation_starts_at=timezone.now() + timedelta(hours=1),
        )
        self.assertTrue(equipment.candidate_complete, equipment.blockers)
        self.assertFalse(equipment.trusted_installation_evidence)

        result = preview_installation_start(
            schedule_status="SCHEDULED",
            stage_one_candidate=True,
            stage_two_candidate=equipment.candidate_complete,
            trusted_equipment_evidence=True,
        )
        self.assertFalse(result.ready_to_start)
        self.assertFalse(result.start_authorized)
        self.assertFalse(result.installation_started)
        self.assertIn(
            "Operational installation-start authority is not implemented.",
            result.blockers,
        )

    def test_consolidated_synthetic_evidence_cannot_start(self):
        from .installation_start_policy_preview import (
            preview_installation_start,
        )

        msr = self.prepare()
        self.serial(msr, 1, "SYNTHETIC-CONSOLIDATED-A")
        self.serial(msr, 2, "SYNTHETIC-CONSOLIDATED-B")

        assessment = self.combined()
        result = preview_installation_start(
            schedule_status="SCHEDULED",
            stage_one_candidate=assessment.stage_one_candidate,
            stage_two_candidate=assessment.stage_two_candidate,
            trusted_equipment_evidence=assessment.trusted_installation_evidence,
        )
        self.assertFalse(result.ready_to_start)
        self.assertFalse(result.start_authorized)
        self.assertFalse(result.installation_started)
    def test_real_stage_one_two_serials_no_invoice_signature(self):
        msr = self.prepare()
        self.stage_one_evidence(msr)
        self.serial(msr, 1, "GOODMAN-REAL-A")
        self.serial(msr, 2, "GOODMAN-REAL-B")
        self.assertFalse(CustomerSignatureEvidence.objects.filter(
            msr=msr,
            document_kind=CustomerSignatureEvidence.DocumentKind.INVOICE,
        ).exists())
        result = self.combined()
        self.assertTrue(result.stage_one_candidate, result.stage_one_blockers)
        self.assertTrue(result.stage_two_candidate, result.stage_two_blockers)
        self.assertTrue(result.combined_candidate)
        self.assertEqual(result.expected_physical_units, 2)

    def test_real_stage_one_and_independent_exception_candidate(self):
        msr = self.prepare()
        self.stage_one_evidence(msr)
        self.serial(msr, 2, "GOODMAN-REAL-B")
        request = self.request(msr)
        decision = self.decide(request)
        self.assertNotEqual(request.created_by_id, decision.created_by_id)
        result = self.combined()
        self.assertTrue(result.stage_one_candidate, result.stage_one_blockers)
        self.assertTrue(result.stage_two_candidate, result.stage_two_blockers)
        self.assertTrue(result.combined_candidate)
        self.assertEqual(result.exception_candidate_units, ("ROW-001-UNIT-001",))

    def test_revoked_exception_blocks_combined_candidate(self):
        msr = self.prepare()
        self.stage_one_evidence(msr)
        self.serial(msr, 2, "GOODMAN-REAL-B")
        self.revoke(self.decide(self.request(msr)))
        result = self.combined()
        self.assertTrue(result.stage_one_candidate, result.stage_one_blockers)
        self.assertFalse(result.stage_two_candidate)
        self.assertFalse(result.combined_candidate)

    def test_missing_contract_blocks_despite_complete_equipment(self):
        msr = self.prepare()
        self.stage_one_evidence(msr, contract=False)
        self.serial(msr, 1, "GOODMAN-REAL-A")
        self.serial(msr, 2, "GOODMAN-REAL-B")
        result = self.combined()
        self.assertFalse(result.stage_one_candidate)
        self.assertTrue(result.stage_two_candidate, result.stage_two_blockers)
        self.assertFalse(result.combined_candidate)

    def test_missing_bank_verified_deposit_blocks(self):
        msr = self.prepare()
        self.stage_one_evidence(msr, deposit=False)
        self.serial(msr, 1, "GOODMAN-REAL-A")
        self.serial(msr, 2, "GOODMAN-REAL-B")
        result = self.combined()
        self.assertFalse(result.stage_one_candidate)
        self.assertTrue(result.stage_two_candidate, result.stage_two_blockers)
        self.assertFalse(result.combined_candidate)

    def test_waiting_period_blocks_despite_complete_equipment(self):
        msr = self.prepare()
        self.stage_one_evidence(msr, signed_days_ago=2)
        self.serial(msr, 1, "GOODMAN-REAL-A")
        self.serial(msr, 2, "GOODMAN-REAL-B")
        result = self.combined()
        self.assertFalse(result.stage_one_candidate)
        self.assertTrue(result.stage_two_candidate, result.stage_two_blockers)
        self.assertFalse(result.combined_candidate)

    def test_missing_unit_blocks_despite_complete_stage_one(self):
        msr = self.prepare()
        self.stage_one_evidence(msr)
        self.serial(msr, 1, "GOODMAN-REAL-A")
        result = self.combined()
        self.assertTrue(result.stage_one_candidate, result.stage_one_blockers)
        self.assertFalse(result.stage_two_candidate)
        self.assertFalse(result.combined_candidate)

    def test_duplicate_serial_evidence_blocks(self):
        msr = self.prepare()
        self.stage_one_evidence(msr)
        first = self.serial(msr, 1, "GOODMAN-REAL-A")
        self.serial(msr, 2, "GOODMAN-REAL-B")
        ProjectEvidence.objects.create(
            msr=msr,
            kind=SERIAL_KIND,
            created_by=first.created_by,
            data=dict(first.data),
            digest=canonical_hash(first.data),
        )
        result = self.combined()
        self.assertTrue(result.stage_one_candidate, result.stage_one_blockers)
        self.assertFalse(result.stage_two_candidate)
        self.assertFalse(result.combined_candidate)

    def test_new_approved_msr_invalidates_old_stage_evidence(self):
        msr = self.prepare()
        self.stage_one_evidence(msr)
        self.serial(msr, 1, "GOODMAN-REAL-A")
        self.serial(msr, 2, "GOODMAN-REAL-B")
        self.assertTrue(self.combined().combined_candidate)
        revised = self.make_synthetic_approved_revision(msr)
        self.assertNotEqual(revised.pk, msr.pk)
        result = self.combined()
        self.assertFalse(result.stage_one_candidate)
        self.assertFalse(result.stage_two_candidate)
        self.assertFalse(result.combined_candidate)

    def test_later_cancellation_deadline_blocks(self):
        msr = self.prepare()
        self.stage_one_evidence(
            msr, cancellation_days_after_signature=15
        )
        self.serial(msr, 1, "GOODMAN-REAL-A")
        self.serial(msr, 2, "GOODMAN-REAL-B")
        result = self.combined()
        self.assertFalse(result.stage_one_candidate)
        self.assertTrue(result.stage_two_candidate, result.stage_two_blockers)
        self.assertFalse(result.combined_candidate)

    def test_serial_captured_after_installation_start_blocks(self):
        msr = self.prepare()
        self.stage_one_evidence(msr)
        first = self.serial(msr, 1, "GOODMAN-REAL-A")
        self.serial(msr, 2, "GOODMAN-REAL-B")
        result = self.combined(
            installation_starts_at=first.created_at - timedelta(seconds=1)
        )
        self.assertTrue(result.stage_one_candidate, result.stage_one_blockers)
        self.assertFalse(result.stage_two_candidate)
        self.assertFalse(result.combined_candidate)

    def test_conflicting_recorded_serial_blocks(self):
        msr = self.prepare()
        self.stage_one_evidence(msr)
        first = self.serial(msr, 1, "GOODMAN-REAL-A")
        self.serial(msr, 2, "GOODMAN-REAL-B")
        payload = dict(first.data)
        payload["unit_id"] = "ROW-001-UNIT-002"
        ProjectEvidence.objects.create(
            msr=msr,
            kind=SERIAL_KIND,
            created_by=first.created_by,
            data=payload,
            digest=canonical_hash(payload),
        )
        result = self.combined()
        self.assertTrue(result.stage_one_candidate, result.stage_one_blockers)
        self.assertFalse(result.stage_two_candidate)
        self.assertFalse(result.combined_candidate)

    def test_duplicate_serial_number_capture_is_rejected(self):
        from rest_framework.exceptions import ValidationError
        msr = self.prepare()
        self.stage_one_evidence(msr)
        self.serial(msr, 1, "GOODMAN-REAL-A")
        with self.assertRaises(ValidationError):
            self.serial(msr, 2, "GOODMAN-REAL-A")
        self.assertEqual(
            ProjectEvidence.objects.filter(
                msr=msr, kind=SERIAL_KIND
            ).count(), 1
        )
        result = self.combined()
        self.assertTrue(result.stage_one_candidate, result.stage_one_blockers)
        self.assertFalse(result.stage_two_candidate)
        self.assertFalse(result.combined_candidate)

    def prepare_ceo_payment_exception(self, msr, *, approve=False):
        request = request_payment_exception(
            actor=self.sales,
            project_id=self.project.pk,
            msr_id=msr.pk,
            reason="Synthetic customer requests payment after completion.",
        )
        if not approve:
            return request, None
        ceo = User.objects.create_user(
            username="combined_payment_exception_ceo",
            password="synthetic-test-only",
            role=Role.CEO,
            initials="CE",
        )
        decision = decide_payment_exception(
            actor=ceo,
            exception_id=request.pk,
            approve=True,
            reason="CEO approves this specific MSR payment exception.",
        )
        self.assertNotEqual(decision.requested_by_id, decision.decided_by_id)
        return decision, ceo

    def test_ceo_exception_with_complete_other_evidence(self):
        msr = self.prepare(payment_option="100_PERCENT_COMPLETION")
        self.stage_one_evidence(msr, deposit=False)
        exception, ceo = self.prepare_ceo_payment_exception(msr, approve=True)
        self.assertTrue(has_valid_payment_exception(self.project, msr))
        self.serial(msr, 1, "GOODMAN-CEO-A")
        self.serial(msr, 2, "GOODMAN-CEO-B")
        self.assertFalse(CustomerPayment.objects.filter(msr=msr).exists())
        result = self.combined()
        self.assertTrue(result.stage_one_candidate, result.stage_one_blockers)
        self.assertTrue(result.stage_two_candidate, result.stage_two_blockers)
        self.assertTrue(result.combined_candidate)

    def test_pending_ceo_exception_does_not_satisfy_payment(self):
        msr = self.prepare(payment_option="100_PERCENT_COMPLETION")
        self.stage_one_evidence(msr, deposit=False)
        self.prepare_ceo_payment_exception(msr)
        self.assertFalse(has_valid_payment_exception(self.project, msr))
        self.serial(msr, 1, "GOODMAN-CEO-A")
        self.serial(msr, 2, "GOODMAN-CEO-B")
        result = self.combined()
        self.assertFalse(result.stage_one_candidate)
        self.assertTrue(result.stage_two_candidate, result.stage_two_blockers)
        self.assertFalse(result.combined_candidate)

    def test_revoked_ceo_exception_removes_payment_readiness(self):
        msr = self.prepare(payment_option="100_PERCENT_COMPLETION")
        self.stage_one_evidence(msr, deposit=False)
        exception, ceo = self.prepare_ceo_payment_exception(msr, approve=True)
        self.serial(msr, 1, "GOODMAN-CEO-A")
        self.serial(msr, 2, "GOODMAN-CEO-B")
        self.assertTrue(self.combined().combined_candidate)
        revoke_payment_exception(
            actor=ceo,
            exception_id=exception.pk,
            reason="CEO withdraws this payment exception.",
        )
        self.assertFalse(has_valid_payment_exception(self.project, msr))
        result = self.combined()
        self.assertFalse(result.stage_one_candidate)
        self.assertTrue(result.stage_two_candidate, result.stage_two_blockers)
        self.assertFalse(result.combined_candidate)

    def test_ceo_exception_cannot_replace_signed_contract(self):
        msr = self.prepare(payment_option="100_PERCENT_COMPLETION")
        self.stage_one_evidence(msr, contract=False, deposit=False)
        self.prepare_ceo_payment_exception(msr, approve=True)
        self.serial(msr, 1, "GOODMAN-CEO-A")
        self.serial(msr, 2, "GOODMAN-CEO-B")
        result = self.combined()
        self.assertFalse(result.stage_one_candidate)
        self.assertTrue(result.stage_two_candidate, result.stage_two_blockers)
        self.assertFalse(result.combined_candidate)

    def test_ceo_exception_cannot_bypass_waiting_period(self):
        msr = self.prepare(payment_option="100_PERCENT_COMPLETION")
        self.stage_one_evidence(msr, deposit=False, signed_days_ago=2)
        self.prepare_ceo_payment_exception(msr, approve=True)
        self.serial(msr, 1, "GOODMAN-CEO-A")
        self.serial(msr, 2, "GOODMAN-CEO-B")
        result = self.combined()
        self.assertFalse(result.stage_one_candidate)
        self.assertTrue(result.stage_two_candidate, result.stage_two_blockers)
        self.assertFalse(result.combined_candidate)

    def test_ceo_exception_cannot_replace_serial_identification(self):
        msr = self.prepare(payment_option="100_PERCENT_COMPLETION")
        self.stage_one_evidence(msr, deposit=False)
        self.prepare_ceo_payment_exception(msr, approve=True)
        self.serial(msr, 1, "GOODMAN-CEO-A")
        result = self.combined()
        self.assertTrue(result.stage_one_candidate, result.stage_one_blockers)
        self.assertFalse(result.stage_two_candidate)
        self.assertFalse(result.combined_candidate)

    def test_ceo_exception_cannot_transfer_to_revised_msr(self):
        msr = self.prepare(payment_option="100_PERCENT_COMPLETION")
        self.stage_one_evidence(msr, deposit=False)
        self.prepare_ceo_payment_exception(msr, approve=True)
        self.serial(msr, 1, "GOODMAN-CEO-A")
        self.serial(msr, 2, "GOODMAN-CEO-B")
        self.assertTrue(self.combined().combined_candidate)
        revised = self.make_synthetic_approved_revision(msr)
        self.assertFalse(has_valid_payment_exception(self.project, revised))
        self.assertFalse(has_valid_payment_exception(self.project, msr))
        result = self.combined()
        self.assertFalse(result.stage_one_candidate)
        self.assertFalse(result.stage_two_candidate)
        self.assertFalse(result.combined_candidate)
