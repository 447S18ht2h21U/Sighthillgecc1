"""Connected fictional customer: six PDFs, Invoice stages, and completion gates.

Read-only development acceptance. No sending, signing or operational release.
"""
from copy import deepcopy

from django.test import TestCase

from .approved_document_version_lock_4250 import (
    inspect_version_locked_review,
)
from .approved_project_workflow_checklist_4251 import (
    inspect_project_workflow_checklist,
)
from .dashboard_workflow_evidence_4257 import (
    describe_workflow_evidence,
)
from .invoice_delivery_policy import (
    InvoiceDeliveryState,
    assess_existing_invoice_evidence,
)
from .invoice_three_stage_policy import (
    InvoiceStage,
    assess_equipment_identification,
    assess_post_installation_delivery,
    assess_pre_installation,
)
from .models import Document
from .test_approved_document_lifecycle_integration_4249 import (
    RealLifecycleIntegration4249Tests,
)


class ConnectedCustomerWorkflow4275Tests(TestCase):
    def setUp(self):
        RealLifecycleIntegration4249Tests.setUp(self)
        RealLifecycleIntegration4249Tests.prepare_no_promotion(self)

        self.snapshot_before = deepcopy(self.full_msr.snapshot)
        self.batch = RealLifecycleIntegration4249Tests.render(self)
        self.project.refresh_from_db()

        self.assertEqual(
            self.project.current_approved_id, self.full_msr.pk
        )
        self.assertEqual(self.full_msr.status, "APPROVED")
        self.assertEqual(self.full_msr.number, 3)
        self.assertEqual(len(self.batch["pdfs"]), 6)

    def assert_no_operational_promotion(self):
        self.full_msr.refresh_from_db()
        self.assertEqual(self.full_msr.snapshot, self.snapshot_before)
        self.assertEqual(Document.objects.count(), 0)

        lifecycle = inspect_version_locked_review(
            project=self.project, msr=self.full_msr, batch=self.batch
        )
        self.assertFalse(lifecycle.installation_authorized)
        self.assertFalse(lifecycle.project_completion_authorized)
        self.assertTrue(all(
            not item.signed_evidence_verified
            and not item.customer_delivery_verified
            and not item.completion_evidence_verified
            for item in lifecycle.documents
        ))

    def test_01_approved_documents_do_not_replace_pre_install_evidence(self):
        assessment = assess_pre_installation(
            approved_msr=True,
            contract_signed=False,
            cancellation_cleared=False,
            waiting_period_cleared=False,
            payment_cleared=False,
        )

        self.assertEqual(assessment.stage, InvoiceStage.PRE_INSTALLATION)
        self.assertEqual(
            assessment.outstanding,
            (
                "contract_signed",
                "cancellation_cleared",
                "waiting_period_cleared",
                "payment_cleared",
            ),
        )
        self.assertFalse(assessment.requirements_satisfied)
        self.assertFalse(assessment.installation_authorized)

        # Even all-positive hypothetical flags are not verified evidence
        # and cannot grant installation authority through this policy.
        hypothetical = assess_pre_installation(
            approved_msr=True,
            contract_signed=True,
            cancellation_cleared=True,
            waiting_period_cleared=True,
            payment_cleared=True,
        )
        self.assertTrue(hypothetical.requirements_satisfied)
        self.assertFalse(hypothetical.installation_authorized)

        self.assert_no_operational_promotion()
        print("PASS: Signed Contract, waiting, cancellation and payment stay separate.")

    def test_02_pdf_equipment_models_cannot_replace_physical_identification(self):
        incomplete = assess_equipment_identification(
            physical_units_accounted_for=False,
            serials_recorded_or_exceptions_approved=False,
        )
        self.assertEqual(
            incomplete.stage, InvoiceStage.EQUIPMENT_IDENTIFICATION
        )
        self.assertEqual(len(incomplete.outstanding), 2)
        self.assertFalse(incomplete.requirements_satisfied)
        self.assertFalse(incomplete.installation_authorized)

        hypothetical = assess_equipment_identification(
            physical_units_accounted_for=True,
            serials_recorded_or_exceptions_approved=True,
        )
        self.assertTrue(hypothetical.requirements_satisfied)
        self.assertFalse(hypothetical.installation_authorized)

        self.assert_no_operational_promotion()
        print("PASS: Printed equipment models cannot replace physical serial evidence.")

    def test_03_post_install_invoice_and_receipt_do_not_prove_delivery(self):
        delivery = assess_existing_invoice_evidence(
            document_generated=True,
            release_review_approved=True,
            delivery_claimed=True,
        )
        self.assertEqual(
            delivery.state, InvoiceDeliveryState.DELIVERY_UNVERIFIED
        )
        self.assertFalse(delivery.installation_evidence_accepted)

        post = assess_post_installation_delivery(
            installation_completed=False,
            final_invoice_prepared=True,
            versioned_addendum_prepared=False,
            independently_verified_delivery=False,
        )
        self.assertEqual(
            post.stage, InvoiceStage.POST_INSTALLATION_DELIVERY
        )
        self.assertFalse(post.requirements_satisfied)
        self.assertEqual(
            post.outstanding,
            (
                "installation_completed",
                "versioned_addendum_prepared",
                "independently_verified_delivery",
            ),
        )
        self.assertFalse(post.delivery_verified)

        # The pure policy cannot authenticate external delivery,
        # even if all four hypothetical inputs are True.
        hypothetical = assess_post_installation_delivery(
            installation_completed=True,
            final_invoice_prepared=True,
            versioned_addendum_prepared=True,
            independently_verified_delivery=True,
        )
        self.assertTrue(hypothetical.requirements_satisfied)
        self.assertFalse(hypothetical.delivery_verified)
        self.assertFalse(hypothetical.installation_authorized)

        self.assert_no_operational_promotion()
        print("PASS: Final invoice and Receipt previews never prove delivery.")

    def test_04_same_customer_checklist_remains_blocked_for_completion(self):
        checklist = inspect_project_workflow_checklist(
            project=self.project,
            msr=self.full_msr,
            batch=self.batch,
        )
        self.assertEqual(checklist.msr_id, str(self.full_msr.pk))
        self.assertEqual(checklist.msr_version, 3)
        self.assertEqual(checklist.document_count, 6)

        statuses = {item.code: item.status for item in checklist.items}
        self.assertEqual(statuses["MSR_BINDING"], "VERIFIED")
        self.assertEqual(
            statuses["PDF_PREVIEWS"], "VERIFIED_REVIEW_ONLY"
        )
        for code in (
            "CONTRACT_PAYMENT",
            "INSTALLATION",
            "FINAL_INVOICE",
            "COMPLETION",
        ):
            self.assertEqual(statuses[code], "NOT_EVALUATED")

        self.assertFalse(checklist.installation_authorized)
        self.assertFalse(checklist.project_completion_authorized)

        evidence = describe_workflow_evidence(self.project)
        self.assertTrue(evidence["read_only"])
        self.assertEqual(
            evidence["statuses"]["approved_msr"], "VERIFIED"
        )
        self.assertEqual(
            evidence["statuses"]["final_invoice_delivery"],
            "NOT_EVALUATED",
        )
        self.assertEqual(
            evidence["statuses"]["receipt_delivery"],
            "NOT_EVALUATED",
        )
        self.assertEqual(
            evidence["statuses"]["completed_docusign"],
            "NOT_EVALUATED",
        )
        self.assertEqual(
            evidence["statuses"]["project_completion"], "BLOCKED"
        )
        self.assertFalse(evidence["installation_authorized"])
        self.assertFalse(evidence["project_completion_authorized"])

        self.assert_no_operational_promotion()
        print("PASS: Real project checklist and dashboard remain blocked.")