"""Acceptance for actual OAuth challenge creation, without provider access."""
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied

from . import docusign
from .models import DocusignChallenge
from .test_installation_envelope_binding_4976 import (
    InspectionEnvelopeBindingDatabase4976 as Fixture,
    ACCOUNT,
)
from .installation_provider_oauth_4979 import begin, OPERATION

CONFIG = {
    "account_id": ACCOUNT,
    "client_id": "synthetic-development-client",
    "client_secret": "synthetic-development-secret",
    "redirect_uri": "http://127.0.0.1:8000/api/docusign/callback/",
    "blockers": [],
}


@override_settings(DEBUG=True, ENVIRONMENT="development")
class RealInspectionChallenge4981(TestCase):
    def setUp(self):
        Fixture.setUp(self)
        self.binding, created = Fixture.bind(self)
        self.assertTrue(created)

    def start(self, *, session_key="isolated-session-4981", actor=None):
        reviewer = self.actor if actor is None else actor
        with (
            patch(
                "core.installation_provider_oauth_4979.docusign.configuration",
                return_value=CONFIG,
            ),
            patch.object(
                docusign,
                "configuration",
                return_value=CONFIG,
            ),
            patch.object(
                docusign,
                "configuration_digest",
                return_value="a" * 64,
            ),
        ):
            return begin(
                actor=reviewer,
                project_id=self.project.pk,
                binding_id=self.binding.pk,
                session_key=session_key,
            )

    def test_real_challenge_persists_bound_operation(self):
        before = DocusignChallenge.objects.count()
        result = self.start()
        self.assertEqual(
            DocusignChallenge.objects.count(), before + 1
        )

        challenge = DocusignChallenge.objects.latest("pk")
        context = challenge.context

        self.assertEqual(context["operation"], OPERATION)
        self.assertEqual(
            context["binding_id"], str(self.binding.pk)
        )
        self.assertEqual(
            context["project_id"], str(self.project.pk)
        )
        self.assertEqual(
            context["retained_inspection_id"], str(self.retained.pk)
        )
        self.assertEqual(context["account_id"], ACCOUNT)
        self.assertEqual(context["reviewer_id"], str(self.actor.pk))
        self.assertFalse(context["send_enabled"])
        self.assertEqual(challenge.actor_id, self.actor.pk)
        self.assertEqual(
            challenge.session_digest,
            docusign.digest("isolated-session-4981"),
        )

        self.assertFalse(result["send_enabled"])
        self.assertFalse(result["provider_signature_verified"])
        self.assertFalse(result["project_completion_authorized"])
        self.assertNotIn("access_token", str(result).lower())

    def test_missing_session_rejected_before_challenge(self):
        before = DocusignChallenge.objects.count()
        with self.assertRaises(PermissionDenied):
            self.start(session_key="")
        self.assertEqual(DocusignChallenge.objects.count(), before)

    def test_wrong_binding_rejected_before_challenge(self):
        before = DocusignChallenge.objects.count()
        with self.assertRaises(ValidationError):
            with (
                patch(
                    "core.installation_provider_oauth_4979.docusign.configuration",
                    return_value=CONFIG,
                ),
                patch.object(
                    docusign, "configuration", return_value=CONFIG
                ),
            ):
                begin(
                    actor=self.actor,
                    project_id=self.project.pk,
                    binding_id="00000000-0000-0000-0000-000000000000",
                    session_key="isolated-session-4981",
                )
        self.assertEqual(DocusignChallenge.objects.count(), before)

    def test_production_disabled_before_challenge(self):
        before = DocusignChallenge.objects.count()
        with override_settings(
            DEBUG=False, ENVIRONMENT="production"
        ):
            with self.assertRaises(PermissionDenied):
                self.start()
        self.assertEqual(DocusignChallenge.objects.count(), before)
