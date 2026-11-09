"""Dashboard guidance does not change milestones or authorization."""
from django.test import SimpleTestCase
from .dashboard_guidance import GUIDANCE, project_guidance


class DashboardGuidanceTests(SimpleTestCase):
    def test_all_six_existing_stages_are_covered(self):
        self.assertEqual(set(GUIDANCE), {
            "completed_customer_record",
            "contracted_for_work",
            "invoice_signed",
            "installation_scheduled",
            "installation_complete",
            "payment_received",
        })

    def test_draft_requires_completion(self):
        result = project_guidance("DRAFT", "installation_scheduled")
        self.assertEqual(result["label"], "Complete the draft MSR")

    def test_submitted_requires_authorized_review(self):
        result = project_guidance("SUBMITTED", "payment_received")
        self.assertIn("authorized reviewer", result["detail"])

    def test_rejection_requires_correction(self):
        result = project_guidance("REJECTED", "completed_customer_record")
        self.assertIn("rejection reason", result["detail"])

    def test_revised_is_not_approved(self):
        result = project_guidance("REVISED", "installation_scheduled")
        self.assertEqual(result["label"], "Complete the draft MSR")

    def test_approved_scheduled_project_gets_readiness_guidance(self):
        result = project_guidance("APPROVED", "installation_scheduled")
        self.assertIn("waiting periods", result["detail"])
        self.assertTrue(result["read_only"])

    def test_generated_documents_not_declared_signed(self):
        for stage in ("contracted_for_work", "invoice_signed"):
            with self.subTest(stage=stage):
                result = project_guidance("APPROVED", stage)
                self.assertIn("generated", result["detail"].lower())

    def test_cancelled_project_does_not_get_work_instruction(self):
        result = project_guidance("CANCELLED", "installation_scheduled")
        self.assertIn("reopening", result["detail"])

    def test_payment_does_not_claim_balance_is_settled(self):
        result = project_guidance("APPROVED", "payment_received")
        self.assertIn("remaining balance", result["detail"])

    def test_unknown_stage_fails_closed(self):
        with self.assertRaises(ValueError):
            project_guidance("APPROVED", "invented_stage")

    def test_invalid_state_type_fails_closed(self):
        with self.assertRaises(ValueError):
            project_guidance(None, "installation_scheduled")

    def test_guidance_is_consistent_and_stateless(self):
        first = project_guidance("APPROVED", "payment_received")
        first["label"] = "Changed"
        second = project_guidance("APPROVED", "payment_received")
        self.assertNotEqual(first["label"], second["label"])
