"""Tests the actual approved PDF renderer's checkbox geometry."""
from dataclasses import replace
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError

from .test_installation_attestation_pdf_4942 import manifest
from .installation_inspection_form_4945 import (
    render_unsigned_inspection_form,
)
from .installation_docusign_contract_4959 import (
    build_unsigned_installation_docusign_contract,
)
from .installation_docusign_placement_4960 import (
    build_offline_inspection_tab_plan,
    _extract_checkbox_rows,
)


FORM = "core.installation_inspection_form_4945"
CONTRACT = "core.installation_docusign_contract_4959"


def actual_form_and_contract():
    actor = SimpleNamespace(pk="synthetic-ceo-4960")
    signing_manifest = manifest()

    with patch(
        FORM + ".build_installation_signing_manifest",
        return_value=signing_manifest,
    ):
        form = render_unsigned_inspection_form(
            actor=actor,
            project_id="synthetic-project-4960",
        )

    with (
        patch(
            CONTRACT + ".build_installation_signing_manifest",
            return_value=signing_manifest,
        ),
        patch(
            CONTRACT + ".render_unsigned_inspection_form",
            return_value=form,
        ),
    ):
        contract = build_unsigned_installation_docusign_contract(
            actor=actor,
            project_id="synthetic-project-4960",
        )

    return form, contract


class ActualInspectionTabPlacement4960Tests(TestCase):
    def test_real_pdf_contains_eight_answer_rows(self):
        form, contract = actual_form_and_contract()
        height, rows = _extract_checkbox_rows(form.pdf)
        self.assertEqual(height, 792)
        self.assertEqual(len(rows), 8)

    def test_five_manager_groups_are_exactly_ten_tabs(self):
        form, contract = actual_form_and_contract()
        plan = build_offline_inspection_tab_plan(
            contract=contract, pdf_bytes=form.pdf
        )
        self.assertEqual(len(plan.radio_positions), 10)
        self.assertEqual(
            tuple(item.choice for item in plan.radio_positions),
            ("YES", "NO") * 5,
        )

    def test_manager_tabs_match_real_pdf_checkbox_positions(self):
        form, contract = actual_form_and_contract()
        height, rows = _extract_checkbox_rows(form.pdf)
        plan = build_offline_inspection_tab_plan(
            contract=contract, pdf_bytes=form.pdf
        )
        for index, field_id in enumerate(
            f"inspection_{i}" for i in range(1, 6)
        ):
            pair = plan.radio_positions[index * 2:index * 2 + 2]
            self.assertEqual(
                tuple(item.field_id for item in pair),
                (field_id, field_id),
            )
            self.assertEqual(
                tuple(item.x for item in pair),
                (426, 488),
            )
            self.assertEqual(
                tuple(item.y for item in pair),
                (round(height - (rows[index] + 9)),) * 2,
            )

    def test_survey_rows_receive_no_manager_tabs(self):
        form, contract = actual_form_and_contract()
        height, rows = _extract_checkbox_rows(form.pdf)
        plan = build_offline_inspection_tab_plan(
            contract=contract, pdf_bytes=form.pdf
        )
        survey_tops = {
            round(height - (row + 9)) for row in rows[5:]
        }
        self.assertTrue(all(
            item.y not in survey_tops
            for item in plan.radio_positions
        ))

    def test_signature_and_date_anchors_preserved(self):
        form, contract = actual_form_and_contract()
        plan = build_offline_inspection_tab_plan(
            contract=contract, pdf_bytes=form.pdf
        )
        self.assertIn(
            plan.signature_anchor.encode(), form.pdf
        )
        self.assertIn(
            plan.date_signed_anchor.encode(), form.pdf
        )

    def test_fingerprint_is_deterministic(self):
        form, contract = actual_form_and_contract()
        first = build_offline_inspection_tab_plan(
            contract=contract, pdf_bytes=form.pdf
        )
        second = build_offline_inspection_tab_plan(
            contract=contract, pdf_bytes=form.pdf
        )
        self.assertEqual(first.plan_sha256, second.plan_sha256)

    def test_different_pdf_bytes_rejected(self):
        form, contract = actual_form_and_contract()
        with self.assertRaises(ValidationError):
            build_offline_inspection_tab_plan(
                contract=contract,
                pdf_bytes=form.pdf + b"modified",
            )

    def test_missing_boxes_rejected(self):
        form, contract = actual_form_and_contract()
        altered = form.pdf.replace(
            b"426 ", b"427 ", 1
        )
        if altered == form.pdf:
            self.skipTest("PDF rectangle encoding unavailable.")
        with self.assertRaises(ValidationError):
            _extract_checkbox_rows(altered)

    def test_forged_provider_trust_rejected(self):
        form, contract = actual_form_and_contract()
        changed = replace(
            contract, provider_signature_verified=True
        )
        with self.assertRaises(ValidationError):
            build_offline_inspection_tab_plan(
                contract=changed, pdf_bytes=form.pdf
            )

    def test_plan_never_asserts_authority(self):
        form, contract = actual_form_and_contract()
        plan = build_offline_inspection_tab_plan(
            contract=contract, pdf_bytes=form.pdf
        )
        self.assertFalse(plan.provider_tabs_installed)
        self.assertFalse(plan.envelope_created)
        self.assertFalse(plan.provider_authenticated)
        self.assertFalse(plan.inspection_findings_verified)
        self.assertFalse(plan.customer_survey_authenticated)
        self.assertFalse(plan.completion_authorized)
