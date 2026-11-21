"""Disposable-database draft tracking status acceptance."""
import os
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.test_post_installation_acceptance_4819 import (
    PostInstallationAcceptance4819 as Fixture,
)
from core.test_installation_draft_end_to_end_5259 import (
    InspectionDraftEndToEnd5259 as Chain,
)
from core.installation_sandbox_draft_transport_5173 import (
    SandboxDraftCreation5173,
)
from core.installation_draft_tracking_5265 import (
    reserve, record_created_draft,
)
from core.installation_draft_status_5266 import status

ACCOUNT = "73fa3720-0d83-4dc5-a081-ab5ba6fb8160"
ENVELOPE = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


@override_settings(DEBUG=True, ENVIRONMENT="development")
class DraftStatus5266(TestCase):
    setUp = Fixture.setUp
    capture = Fixture.capture
    review = Fixture.review
    establish_source = Chain.establish_source
    prepare_and_authorize = Chain.prepare_and_authorize

    def read(self):
        return status(
            actor=self.fixture.manager,
            project_id=self.project.pk,
        )

    def authorize_flag(self):
        return patch.dict(os.environ, {
            "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED": "1",
        })

    def assert_safe(self, value):
        self.assertTrue(value["read_only"])
        self.assertFalse(value["automatic_retry_allowed"])
        self.assertFalse(value["send_authorized"])
        self.assertFalse(value["signature_verified"])
        self.assertFalse(value["receipt_authorized"])
        self.assertFalse(value["completion_authorized"])

    def test_no_attempt_is_visible_without_authority(self):
        self.prepare_and_authorize()
        with self.authorize_flag():
            result = self.read()
        self.assertEqual(result["state"], "NO_DRAFT_ATTEMPT")
        self.assertFalse(result["manual_reconciliation_required"])
        self.assert_safe(result)

    def test_ambiguous_attempt_requires_manual_reconciliation(self):
        self.prepare_and_authorize()
        with self.authorize_flag():
            reservation = reserve(
                actor=self.fixture.manager,
                project_id=self.project.pk,
            )
            result = self.read()
        self.assertEqual(result["state"], "PROVIDER_OUTCOME_UNKNOWN")
        self.assertEqual(
            result["reservation_id"], str(reservation.pk)
        )
        self.assertTrue(result["manual_reconciliation_required"])
        self.assert_safe(result)

    def test_recorded_draft_remains_unsent_and_non_authorizing(self):
        self.prepare_and_authorize()
        with self.authorize_flag():
            reservation = reserve(
                actor=self.fixture.manager,
                project_id=self.project.pk,
            )
            record_created_draft(
                actor=self.fixture.manager,
                reservation=reservation,
                response=SandboxDraftCreation5173(
                    account_id=ACCOUNT,
                    envelope_id=ENVELOPE,
                    status="created",
                ),
            )
            result = self.read()
        self.assertEqual(
            result["state"], "SANDBOX_DRAFT_CREATED_NOT_SENT"
        )
        self.assertEqual(result["provider_envelope_id"], ENVELOPE)
        self.assertFalse(result["manual_reconciliation_required"])
        self.assert_safe(result)

    def test_unauthorized_role_cannot_read_draft_status(self):
        self.prepare_and_authorize()
        with self.authorize_flag():
            from django.core.exceptions import PermissionDenied
            with self.assertRaises(PermissionDenied):
                status(
                    actor=self.inspector,
                    project_id=self.project.pk,
                )
