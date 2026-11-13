"""Focused non-network acceptance for completion handoff safeguards."""
import os
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError

from . import test_completion_provider_transport_4630 as fixtures
from .completion_provider_transport_4630 import (
    simulate_sandbox_draft_post,
)


@override_settings(DEBUG=True, ENVIRONMENT="development")
class CompletionProviderHandoffSafetyTests(TestCase):
    setUp = fixtures.CompletionProviderTransportTests.setUp
    token = fixtures.CompletionProviderTransportTests.token

    def test_transport_disabled_by_default(self):
        with patch.dict(
            os.environ,
            {"GECC_TEST_COMPLETION_TRANSPORT": "0"},
        ):
            calls = []
            with self.assertRaises(ValidationError):
                simulate_sandbox_draft_post(
                    prepared=self.prepared,
                    access_token=self.token(),
                    test_transport=lambda request: calls.append(request),
                )
            self.assertEqual(calls, [])

    @override_settings(ENVIRONMENT="production")
    def test_transport_disabled_outside_development(self):
        with patch.dict(
            os.environ,
            {"GECC_TEST_COMPLETION_TRANSPORT": "1"},
        ):
            calls = []
            with self.assertRaises(ValidationError):
                simulate_sandbox_draft_post(
                    prepared=self.prepared,
                    access_token=self.token(),
                    test_transport=lambda request: calls.append(request),
                )
            self.assertEqual(calls, [])

    def test_transport_does_not_use_implicit_network(self):
        with patch.dict(
            os.environ,
            {"GECC_TEST_COMPLETION_TRANSPORT": "1"},
        ):
            with self.assertRaises(ValidationError):
                simulate_sandbox_draft_post(
                    prepared=self.prepared,
                    access_token=self.token(),
                )

    def test_handoff_requires_database_and_verified_identity(self):
        from .completion_provider_handoff_4631 import (
            prepare_verified_handoff,
        )
        with self.assertRaises(ValidationError):
            prepare_verified_handoff(
                actor=None,
                attempt_id=self.attempt,
                verification_id=self.envelope,
            )
