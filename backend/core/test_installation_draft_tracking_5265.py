"""Real-model, isolated duplicate-prevention acceptance."""
import os
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.models import ProjectEvidence
from core.test_post_installation_acceptance_4819 import (
    PostInstallationAcceptance4819 as Fixture,
)
from core.test_installation_draft_end_to_end_5259 import (
    InspectionDraftEndToEnd5259 as Chain,
)
from core.installation_sandbox_draft_transport_5173 import (
    SandboxDraftCreation5173,
)
from core import installation_draft_tracking_5265 as tracking

ACCOUNT = "73fa3720-0d83-4dc5-a081-ab5ba6fb8160"
ENVELOPE = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
TOKEN = "synthetic_not_real_token_5265"


@override_settings(DEBUG=True, ENVIRONMENT="development")
class DraftTracking5265(TestCase):
    setUp = Fixture.setUp
    capture = Fixture.capture
    review = Fixture.review
    establish_source = Chain.establish_source
    prepare_and_authorize = Chain.prepare_and_authorize

    def run_tracked(self):
        return tracking.create_tracked_sandbox_draft(
            actor=self.fixture.manager,
            project_id=self.project.pk,
            account_id=ACCOUNT,
            bearer_token=TOKEN,
        )

    def flags(self):
        return patch.dict(os.environ, {
            "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED": "1",
            "GECC_IM_SANDBOX_DRAFT_CREATE_ENABLED": "1",
        })

    def response(self):
        return SandboxDraftCreation5173(
            account_id=ACCOUNT,
            envelope_id=ENVELOPE,
            status="created",
        )

    def test_created_draft_is_recorded_once_and_never_sent(self):
        self.prepare_and_authorize()
        with (
            self.flags(),
            patch.object(
                tracking,
                "create_authorized_sandbox_draft",
                return_value=self.response(),
            ) as provider,
        ):
            result = self.run_tracked()
            self.assertEqual(result.status, "created")
            provider.assert_called_once()

            reservations = ProjectEvidence.objects.filter(
                msr=self.msr, kind=tracking.RESERVATION_KIND
            )
            outcomes = ProjectEvidence.objects.filter(
                msr=self.msr, kind=tracking.RESULT_KIND
            )
            self.assertEqual(reservations.count(), 1)
            self.assertEqual(outcomes.count(), 1)
            self.assertEqual(
                outcomes.first().data["provider_envelope_id"],
                ENVELOPE,
            )
            self.assertIs(
                outcomes.first().data["send_authorized"], False
            )
            self.assertNotIn(
                TOKEN, str(reservations.first().data)
            )
            self.assertNotIn(
                TOKEN, str(outcomes.first().data)
            )

            with self.assertRaises(ValidationError):
                self.run_tracked()
            provider.assert_called_once()

    def test_ambiguous_failure_remains_reserved_no_retry(self):
        self.prepare_and_authorize()
        with (
            self.flags(),
            patch.object(
                tracking,
                "create_authorized_sandbox_draft",
                side_effect=RuntimeError(
                    "Synthetic uncertain provider outcome"
                ),
            ) as provider,
        ):
            with self.assertRaises(RuntimeError):
                self.run_tracked()

            self.assertEqual(
                ProjectEvidence.objects.filter(
                    msr=self.msr,
                    kind=tracking.RESERVATION_KIND,
                ).count(), 1
            )
            self.assertFalse(
                ProjectEvidence.objects.filter(
                    msr=self.msr,
                    kind=tracking.RESULT_KIND,
                ).exists()
            )

            with self.assertRaises(ValidationError):
                self.run_tracked()
            provider.assert_called_once()

    def test_disabled_transport_creates_no_reservation(self):
        self.prepare_and_authorize()
        with (
            patch.dict(os.environ, {
                "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED": "1",
                "GECC_IM_SANDBOX_DRAFT_CREATE_ENABLED": "0",
            }),
            patch.object(
                tracking,
                "create_authorized_sandbox_draft",
            ) as provider,
        ):
            from django.core.exceptions import PermissionDenied

            with self.assertRaises(PermissionDenied):
                self.run_tracked()

            provider.assert_not_called()
            self.assertFalse(
                ProjectEvidence.objects.filter(
                    msr=self.msr,
                    kind=tracking.RESERVATION_KIND,
                ).exists()
            )
