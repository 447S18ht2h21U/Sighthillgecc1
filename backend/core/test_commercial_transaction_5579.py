"""Isolated commercial signing transaction regression tests.

No provider network calls or acceptance database access.
"""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Role
from .commercial_signing_5567 import (
    authorize_sender,
    controlled_commercial_recipients,
)
from .commercial_read_oauth_5576 import authorized_reader
from .commercial_reconciliation_5575 import check_completion
from .commercial_send_callback_5573 import send_once


class CommercialTransactionRegressionTests(SimpleTestCase):

    def setUp(self):
        self.project = SimpleNamespace(reviewer_id="manager-1")
        self.manager = SimpleNamespace(
            id="manager-1", role=Role.SALES_MANAGER, is_active=True
        )
        self.ceo = SimpleNamespace(
            id="ceo-1", role=Role.CEO, is_active=True
        )
        self.comptroller = SimpleNamespace(
            id="comptroller-1", role=Role.COMPTROLLER, is_active=True
        )
        self.associate = SimpleNamespace(
            id="associate-1", role=Role.SALES_ASSOCIATE, is_active=True
        )

    def test_assigned_manager_and_ceo_can_authorize(self):
        authorize_sender(self.manager, self.project)
        authorize_sender(self.ceo, self.project)

    def test_other_roles_cannot_authorize_commercial_sending(self):
        for actor in (self.comptroller, self.associate):
            with self.subTest(role=actor.role):
                with self.assertRaises(PermissionDenied):
                    authorize_sender(actor, self.project)

    def test_unassigned_or_inactive_manager_cannot_send(self):
        other = SimpleNamespace(
            id="manager-2", role=Role.SALES_MANAGER, is_active=True
        )
        inactive = SimpleNamespace(
            id="manager-1", role=Role.SALES_MANAGER, is_active=False
        )
        for actor in (other, inactive):
            with self.assertRaises(PermissionDenied):
                authorize_sender(actor, self.project)

    def test_commercial_read_access_is_distinct_from_send_access(self):
        authorized_reader(self.comptroller, self.project)
        authorized_reader(self.manager, self.project)
        authorized_reader(self.ceo, self.project)
        with self.assertRaises(PermissionDenied):
            authorized_reader(self.associate, self.project)

    def test_controlled_recipients_are_required(self):
        review = {
            "customer": {"email": "customer@controlled-mail.com"},
            "gecc": {"email": "gecc@controlled-mail.com"},
        }
        allowed = (
            "customer@controlled-mail.com,gecc@controlled-mail.com"
        )
        with patch.dict(
            "os.environ",
            {"GECC_COMMERCIAL_SANDBOX_TEST_EMAILS": allowed},
        ):
            self.assertEqual(
                controlled_commercial_recipients(review),
                ("customer@controlled-mail.com", "gecc@controlled-mail.com"),
            )
            changed = {
                **review,
                "customer": {"email": "other@controlled-mail.com"},
            }
            with self.assertRaises(ValidationError):
                controlled_commercial_recipients(changed)

    def test_both_signers_must_have_valid_completion_evidence(self):
        summary = {
            "completedDateTime": "2020-01-03T10:00:00+00:00"
        }
        recipients = {
            "signers": [
                {
                    "recipientId": "1",
                    "status": "completed",
                    "signedDateTime": "2020-01-01T10:00:00+00:00",
                },
                {
                    "recipientId": "2",
                    "status": "completed",
                    "signedDateTime": "2020-01-02T10:00:00+00:00",
                },
            ]
        }
        completed, signers = check_completion(summary, recipients)
        self.assertTrue(completed)
        self.assertEqual(set(signers), {"1", "2"})

        incomplete = {
            "signers": [
                recipients["signers"][0],
                {**recipients["signers"][1], "status": "sent"},
            ]
        }
        with self.assertRaises(ValidationError):
            check_completion(summary, incomplete)

    def test_provider_send_failure_is_never_automatically_retried(self):
        payload = {"status": "sent"}
        with patch(
            "core.commercial_send_callback_5573.build_opener"
        ) as opener:
            opener.return_value.open.side_effect = TimeoutError(
                "Simulated uncertain provider outcome"
            )
            with self.assertRaises(ValidationError):
                send_once(
                    "00000000-0000-0000-0000-000000000001",
                    "fictional-test-token",
                    payload,
                )
            self.assertEqual(opener.return_value.open.call_count, 1)
