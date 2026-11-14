"""Offline safety tests for the Installation Manager signing contract."""
from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .installation_attestation_pdf_4942 import (
    SIGNATURE_ANCHOR, DATE_ANCHOR,
)
from .installation_inspection_form_4945 import (
    INSPECTION_ITEMS, INSPECTION_IDS, SURVEY_IDS,
)
from .installation_docusign_contract_4959 import (
    build_unsigned_installation_docusign_contract,
    required_installation_signing_fields,
    validate_five_findings,
)

M = "core.installation_docusign_contract_4959"


def fixtures():
    pdf = (
        b"%PDF-1.4\n"
        + SIGNATURE_ANCHOR.encode()
        + b"\n"
        + DATE_ANCHOR.encode()
        + b"\n%%EOF"
    )
    manifest = SimpleNamespace(
        project_id="project-4959",
        approved_msr_id="msr-4959",
        approved_msr_version=2,
        source_evidence_id="source-4959",
        source_pdf_sha256="a" * 64,
        preparation_evidence_id="preparation-4959",
        attestation_binding_sha256="b" * 64,
        signer_user_id="manager-4959",
        signer_email="manager@example.com",
        signer_name="Installation Manager",
    )
    document = SimpleNamespace(
        pdf=pdf,
        pdf_sha256=sha256(pdf).hexdigest(),
        project_id="project-4959",
        approved_msr_id="msr-4959",
        provider_authenticated=False,
        docusign_tabs_configured=False,
        completion_authorized=False,
    )
    return manifest, document


def build(manifest=None, document=None):
    default_manifest, default_document = fixtures()
    with (
        patch(M + ".settings") as settings,
        patch(
            M + ".build_installation_signing_manifest",
            return_value=manifest or default_manifest,
        ),
        patch(
            M + ".render_unsigned_inspection_form",
            return_value=document or default_document,
        ),
    ):
        settings.ENVIRONMENT = "development"
        settings.DEBUG = True
        return build_unsigned_installation_docusign_contract(
            actor=SimpleNamespace(pk="ceo-4959"),
            project_id="project-4959",
        )


class InstallationSigningContract4959Tests(TestCase):
    def test_exact_five_required_radio_groups(self):
        fields = required_installation_signing_fields()
        self.assertEqual(len(fields), 7)
        self.assertEqual(
            tuple(item.field_id for item in fields[:5]),
            tuple(INSPECTION_IDS),
        )
        self.assertEqual(
            tuple(item.question_text for item in fields[:5]),
            tuple(INSPECTION_ITEMS),
        )
        self.assertTrue(all(field.required for field in fields))
        self.assertTrue(all(
            field.choices == ("YES", "NO")
            for field in fields[:5]
        ))

    def test_signature_and_date_are_separate_required_tabs(self):
        fields = required_installation_signing_fields()
        self.assertEqual(fields[5].field_type, "SIGN_HERE")
        self.assertEqual(fields[5].anchor, SIGNATURE_ANCHOR)
        self.assertEqual(fields[6].field_type, "DATE_SIGNED")
        self.assertEqual(fields[6].anchor, DATE_ANCHOR)

    def test_customer_questions_not_manager_signing_fields(self):
        fields = required_installation_signing_fields()
        self.assertTrue(all(
            field.field_id not in SURVEY_IDS for field in fields
        ))
        self.assertTrue(all(
            field.signer_role == "INSTALLATION_MANAGER"
            for field in fields
        ))

    def test_valid_five_findings_canonicalized(self):
        values = {key: "YES" for key in INSPECTION_IDS}
        values["inspection_4"] = "NO"
        result = validate_five_findings(values)
        self.assertEqual(result[3], ("inspection_4", "NO"))

    def test_missing_and_extra_answers_rejected(self):
        values = {key: "YES" for key in INSPECTION_IDS}
        del values["inspection_1"]
        with self.assertRaises(ValidationError):
            validate_five_findings(values)
        values["inspection_1"] = "YES"
        values["survey_1"] = "NO"
        with self.assertRaises(ValidationError):
            validate_five_findings(values)

    def test_invalid_or_blank_answer_rejected(self):
        values = {key: "YES" for key in INSPECTION_IDS}
        for invalid in (None, "", "PASS", True, "yes"):
            values["inspection_2"] = invalid
            with self.assertRaises(ValidationError):
                validate_five_findings(values)

    def test_contract_never_asserts_provider_trust(self):
        contract = build()
        self.assertEqual(contract.provider, "DOCUSIGN")
        self.assertEqual(contract.project_id, "project-4959")
        self.assertEqual(contract.signer_user_id, "manager-4959")
        self.assertEqual(len(contract.contract_sha256), 64)
        self.assertIsNone(contract.envelope_id)
        self.assertFalse(contract.provider_tabs_installed)
        self.assertFalse(contract.signer_authenticated)
        self.assertFalse(contract.provider_signature_verified)
        self.assertFalse(contract.provider_dates_verified)
        self.assertFalse(contract.inspection_findings_verified)
        self.assertFalse(contract.customer_survey_authenticated)
        self.assertFalse(contract.trusted_installation_evidence)
        self.assertFalse(contract.receipt_issuance_authorized)
        self.assertFalse(contract.project_completion_authorized)

    def test_deterministic_contract_fingerprint(self):
        self.assertEqual(
            build().contract_sha256,
            build().contract_sha256,
        )

    def test_tampered_pdf_fingerprint_rejected(self):
        manifest, document = fixtures()
        modified = SimpleNamespace(
            **{**vars(document), "pdf_sha256": "0" * 64}
        )
        with self.assertRaises(ValidationError):
            build(document=modified)

    def test_wrong_project_binding_rejected(self):
        manifest, document = fixtures()
        modified = SimpleNamespace(
            **{**vars(document), "project_id": "other-project"}
        )
        with self.assertRaises(ValidationError):
            build(document=modified)

    def test_missing_signature_anchor_rejected(self):
        manifest, document = fixtures()
        pdf = document.pdf.replace(
            SIGNATURE_ANCHOR.encode(), b"MISSING_SIGNATURE"
        )
        modified = SimpleNamespace(
            **{
                **vars(document),
                "pdf": pdf,
                "pdf_sha256": sha256(pdf).hexdigest(),
            }
        )
        with self.assertRaises(ValidationError):
            build(document=modified)

    def test_production_disabled(self):
        with patch(M + ".settings") as settings:
            settings.ENVIRONMENT = "production"
            settings.DEBUG = False
            with self.assertRaises(PermissionDenied):
                build_unsigned_installation_docusign_contract(
                    actor=None, project_id="project-4959"
                )
