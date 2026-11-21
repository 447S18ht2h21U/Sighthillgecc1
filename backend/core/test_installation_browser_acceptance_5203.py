"""Step 5203: authenticated HTTP authorization with real evidence."""
import os
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from core.models import AuditEvent, ProjectEvidence, Role, User
from core.installation_draft_authorization_5179 import KIND
from core.installation_draft_browser_api_5185 import authorize
from core.test_installation_independent_acceptance_5202 import (
    IndependentInstallationAcceptance5202 as Fixture,
)


@override_settings(DEBUG=True, ENVIRONMENT="development")
class BrowserAuthorizationAcceptance5203(TestCase):
    setUp = Fixture.setUp
    capture = Fixture.capture
    review = Fixture.review
    prepare_chain = Fixture.prepare_chain

    def request(self, actor, payload):
        factory = APIRequestFactory()
        request = factory.post(
            "/api/inspection-draft-intents/acceptance/authorize/",
            payload,
            format="json",
        )
        force_authenticate(request, user=actor)
        return authorize(request, self.project.pk)

    def test_ceo_browser_authorization_and_duplicate(self):
        with patch.dict(os.environ, {
            "GECC_INSTALL_ATTESTATION_PREP_TEST_ENABLED": "1",
            "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED": "1",
        }):
            self.prepare_chain()
            before = AuditEvent.objects.count()
            payload = {"confirm_inspection_draft_intent": True}

            response = self.request(self.ceo, payload)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(
                response.data["status"], "DRAFT_INTENT_RECORDED"
            )
            self.assertFalse(response.data["send_authorized"])
            self.assertFalse(
                response.data["provider_draft_created"]
            )
            self.assertEqual(
                AuditEvent.objects.count(), before + 1
            )

            duplicate = self.request(self.ceo, payload)
            self.assertEqual(duplicate.status_code, 400)
            self.assertEqual(
                ProjectEvidence.objects.filter(
                    msr=self.msr, kind=KIND
                ).count(), 1
            )
            self.assertEqual(
                AuditEvent.objects.count(), before + 1
            )

    def test_browser_role_and_payload_restrictions(self):
        with patch.dict(os.environ, {
            "GECC_INSTALL_ATTESTATION_PREP_TEST_ENABLED": "1",
            "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED": "1",
        }):
            self.prepare_chain()
            employee = User.objects.create_user(
                username="inspection_5203_associate",
                role=Role.SALES_ASSOCIATE,
                initials="SA",
            )
            before = AuditEvent.objects.count()

            denied = self.request(
                employee,
                {"confirm_inspection_draft_intent": True},
            )
            self.assertEqual(denied.status_code, 403)

            for payload in (
                {"confirm_inspection_draft_intent": False},
                {
                    "confirm_inspection_draft_intent": True,
                    "send_envelope": True,
                },
                {},
            ):
                response = self.request(self.ceo, payload)
                self.assertEqual(response.status_code, 400)

            self.assertFalse(
                ProjectEvidence.objects.filter(
                    msr=self.msr, kind=KIND
                ).exists()
            )
            self.assertEqual(
                AuditEvent.objects.count(), before
            )
