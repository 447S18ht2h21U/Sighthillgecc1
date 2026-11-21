"""Verify real transaction boundaries without TestCase's wrapper.

Uses a disposable SQLite database and a fully mocked provider.
No actual DocuSign requests, credentials, or operational records.
"""
import os
from unittest.mock import patch

from django.db import connection, transaction
from django.test import TransactionTestCase, override_settings
from django.core.exceptions import ValidationError

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
TOKEN = "synthetic_not_real_token_5267"


@override_settings(DEBUG=True, ENVIRONMENT="development")
class DraftTransactionDurability5267(TransactionTestCase):
    setUp = Fixture.setUp
    capture = Fixture.capture
    review = Fixture.review
    establish_source = Chain.establish_source
    prepare_and_authorize = Chain.prepare_and_authorize

    def enabled(self):
        return patch.dict(os.environ, {
            "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED": "1",
            "GECC_IM_SANDBOX_DRAFT_CREATE_ENABLED": "1",
        })

    def invoke(self):
        return tracking.create_tracked_sandbox_draft(
            actor=self.fixture.manager,
            project_id=self.project.pk,
            account_id=ACCOUNT,
            bearer_token=TOKEN,
        )

    def count(self, kind):
        return ProjectEvidence.objects.filter(
            msr=self.msr, kind=kind
        ).count()

    def _fixture_teardown(self):
        # This class contains only one transaction test.
        # Django's normal flush conflicts with protected immutable
        # equipment history. The entire disposable SQLite test
        # database is destroyed when the test command finishes.
        name = connection.settings_dict.get("NAME")
        isolated = (
            connection.vendor == "sqlite"
            and type(name) is str
            and (
                name == ":memory:"
                or (
                    name.startswith("file:memorydb_")
                    and name.endswith("?mode=memory&cache=shared")
                )
            )
        )
        if not isolated:
            raise RuntimeError(
                "STOP: Transaction cleanup exception is isolated-test only."
            )

    def test_failure_preserves_reservation_outside_transaction(self):
        self.prepare_and_authorize()
        observed = []

        def simulated_failure(**kwargs):
            observed.append((
                transaction.get_autocommit(),
                connection.in_atomic_block,
                self.count(tracking.RESERVATION_KIND),
            ))
            raise RuntimeError("Simulated ambiguous provider failure")

        with (
            self.enabled(),
            patch.object(
                tracking,
                "create_authorized_sandbox_draft",
                side_effect=simulated_failure,
            ) as provider,
        ):
            self.assertTrue(transaction.get_autocommit())
            self.assertFalse(connection.in_atomic_block)

            with self.assertRaises(RuntimeError):
                self.invoke()

            self.assertEqual(observed, [(True, False, 1)])
            self.assertTrue(transaction.get_autocommit())
            self.assertFalse(connection.in_atomic_block)
            self.assertEqual(
                self.count(tracking.RESERVATION_KIND), 1
            )
            self.assertEqual(
                self.count(tracking.RESULT_KIND), 0
            )

            with self.assertRaises(ValidationError):
                self.invoke()
            provider.assert_called_once()
