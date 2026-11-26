"""Focused structured installation inspection tests."""

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from .installation_inspection_findings_5996 import (
    ACCEPT,
    CORRECTIONS_REQUIRED,
    SATISFIED,
    UNSATISFIED,
    REQUIRED_FINDINGS,
    validate_inspection_findings,
)


class InstallationInspectionFindingsTests5996(SimpleTestCase):

    def setUp(self):
        self.payload = {
            key: True
            for key in REQUIRED_FINDINGS
        }

        self.payload.update({
            "customer_impression": SATISFIED,
            "inspection_notes": "",
            "decision": ACCEPT,
        })

        self.evidence = {
            "equipment_evidence_verified": True,
            "materials_evidence_verified": True,
            "distributor_invoice_evidence_verified": True,
        }

    def validate(self):
        return validate_inspection_findings(
            self.payload,
            **self.evidence,
        )

    def test_satisfactory_inspection_without_notes(self):
        result = self.validate()

        self.assertTrue(result["findings_validated"])
        self.assertEqual(
            result["requested_decision"], ACCEPT
        )
        self.assertEqual(
            result["inspection_notes"], ""
        )

    def test_every_required_finding_preserved(self):
        result = self.validate()

        self.assertEqual(
            result["findings"],
            {
                key: True
                for key in REQUIRED_FINDINGS
            },
        )

    def test_missing_customer_impression_rejected(self):
        self.payload.pop("customer_impression")

        with self.assertRaises(ValidationError):
            self.validate()

    def test_no_default_customer_impression(self):
        for value in ("", None, "UNKNOWN", True):
            with self.subTest(value=value):
                self.payload["customer_impression"] = value

                with self.assertRaises(ValidationError):
                    self.validate()

    def test_unsatisfied_customer_requires_follow_up(self):
        self.payload["customer_impression"] = UNSATISFIED

        with self.assertRaises(ValidationError):
            self.validate()

    def test_unsatisfied_customer_without_notes_rejected(self):
        self.payload.update({
            "customer_impression": UNSATISFIED,
            "decision": CORRECTIONS_REQUIRED,
        })

        with self.assertRaises(ValidationError):
            self.validate()

    def test_unsatisfied_customer_with_notes_recordable(self):
        self.payload.update({
            "customer_impression": UNSATISFIED,
            "decision": CORRECTIONS_REQUIRED,
            "inspection_notes":
                "Customer reports excessive equipment noise.",
        })

        result = self.validate()

        self.assertTrue(
            result["customer_follow_up_required"]
        )

        self.assertEqual(
            result["requested_decision"],
            CORRECTIONS_REQUIRED,
        )

    def test_deficiency_prevents_acceptance(self):
        for finding in REQUIRED_FINDINGS:
            with self.subTest(finding=finding):
                self.payload[finding] = False

                with self.assertRaises(ValidationError):
                    self.validate()

                self.payload[finding] = True

    def test_corrections_require_explanation(self):
        self.payload.update({
            "job_site_clean": False,
            "decision": CORRECTIONS_REQUIRED,
        })

        with self.assertRaises(ValidationError):
            self.validate()

    def test_corrections_can_be_recorded(self):
        self.payload.update({
            "job_site_clean": False,
            "decision": CORRECTIONS_REQUIRED,
            "inspection_notes":
                "Technician must remove remaining debris.",
        })

        result = self.validate()

        self.assertEqual(
            result["outstanding_findings"],
            ["job_site_clean"],
        )

    def test_personal_inspection_mandatory(self):
        self.payload.update({
            "personally_inspected": False,
            "decision": CORRECTIONS_REQUIRED,
            "inspection_notes":
                "Inspection has not been performed.",
        })

        with self.assertRaises(ValidationError):
            self.validate()

    def test_unverified_distributor_invoice_blocks_confirmation(self):
        self.evidence[
            "distributor_invoice_evidence_verified"
        ] = False

        with self.assertRaises(ValidationError):
            self.validate()

    def test_missing_invoice_can_be_recorded_as_deficiency(self):
        self.evidence[
            "distributor_invoice_evidence_verified"
        ] = False

        self.payload.update({
            "distributor_invoice_uploaded_and_verified": False,
            "decision": CORRECTIONS_REQUIRED,
            "inspection_notes":
                "Distributor invoice must be uploaded and verified.",
        })

        result = self.validate()

        self.assertIn(
            "distributor_invoice_uploaded_and_verified",
            result["outstanding_findings"],
        )

    def test_unverified_equipment_blocks_confirmation(self):
        self.evidence[
            "equipment_evidence_verified"
        ] = False

        with self.assertRaises(ValidationError):
            self.validate()

    def test_unverified_materials_block_confirmation(self):
        self.evidence[
            "materials_evidence_verified"
        ] = False

        with self.assertRaises(ValidationError):
            self.validate()

    def test_client_cannot_supply_evidence_authority(self):
        self.payload[
            "distributor_invoice_evidence_verified"
        ] = True

        with self.assertRaises(ValidationError):
            self.validate()

    def test_false_employee_identity_cannot_be_submitted(self):
        self.payload["inspected_by"] = "other-employee"

        with self.assertRaises(ValidationError):
            self.validate()

    def test_false_inspection_timestamp_cannot_be_submitted(self):
        self.payload["inspected_at"] = "2020-01-01"

        with self.assertRaises(ValidationError):
            self.validate()

    def test_non_boolean_finding_rejected(self):
        self.payload["job_site_clean"] = "true"

        with self.assertRaises(ValidationError):
            self.validate()

    def test_whitespace_only_correction_notes_rejected(self):
        self.payload.update({
            "job_site_clean": False,
            "decision": CORRECTIONS_REQUIRED,
            "inspection_notes": "     ",
        })

        with self.assertRaises(ValidationError):
            self.validate()

    def test_excessive_notes_rejected(self):
        self.payload["inspection_notes"] = "A" * 2001

        with self.assertRaises(ValidationError):
            self.validate()

    def test_unknown_evidence_state_rejected(self):
        self.evidence[
            "distributor_invoice_evidence_verified"
        ] = None

        with self.assertRaises(ValidationError):
            self.validate()

    def test_validation_does_not_grant_operational_authority(self):
        result = self.validate()

        for flag in (
            "installation_acceptance_established",
            "certificate_transmission_authorized",
            "receipt_issuance_authorized",
            "project_completion_authorized",
        ):
            self.assertFalse(result[flag])

    def test_original_request_not_mutated(self):
        before = dict(self.payload)

        self.validate()

        self.assertEqual(self.payload, before)
