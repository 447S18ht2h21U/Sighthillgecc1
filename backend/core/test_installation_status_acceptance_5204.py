"""Step 5204: real evidence and authenticated status API acceptance."""
import os
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from core.models import AuditEvent, ProjectEvidence, Role, User
from core.installation_draft_status_api_5186 import status as status_api
from core.installation_draft_browser_5185 import authorize
from core.installation_draft_authorization_5179 import KIND
from core.installation_source_artifact_4826 import retain_installation_source
from core.test_installation_independent_acceptance_5202 import (
    IndependentInstallationAcceptance5202 as Fixture,
)


@override_settings(DEBUG=True, ENVIRONMENT="development")
class InspectionStatusAcceptance5204(TestCase):
    setUp = Fixture.setUp
    capture = Fixture.capture
    review = Fixture.review
    prepare_chain = Fixture.prepare_chain

    def status_request(self, actor):
        request = APIRequestFactory().get(
            "/api/inspection-draft-intents/test/status/"
        )
        force_authenticate(request, user=actor)
        return status_api(request, self.project.pk)

    def assert_no_provider_authority(self, data):
        for field in (
            "provider_draft_created",
            "provider_request_authorized",
            "send_authorized",
            "provider_signature_verified",
            "project_completion_authorized",
        ):
            self.assertIs(data[field], False)

    def test_readiness_and_authorization_status_lifecycle(self):
        with patch.dict(os.environ, {
            "GECC_INSTALL_ATTESTATION_PREP_TEST_ENABLED": "1",
            "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED": "1",
        }):
            self.ceo = User.objects.create_user(
                username="inspection_5204_ceo",
                role=Role.CEO,
                initials="CE",
            )
            initial = self.status_request(self.ceo)
            self.assertEqual(initial.status_code, 200)
            self.assertFalse(initial.data["preparation_ready"])
            self.assertEqual(initial.data["source_stage"], "SOURCE_NOT_VERIFIED")
            self.assertEqual(
                initial.data["authorization_state"],
                "NOT_AUTHORIZED",
            )
            self.assert_no_provider_authority(initial.data)

            self.prepare_chain()
            ready = self.status_request(self.ceo)
            self.assertEqual(ready.status_code, 200)
            self.assertTrue(ready.data["preparation_ready"])
            self.assertEqual(ready.data["source_stage"], "PREPARATION_VERIFIED")
            self.assertEqual(
                ready.data["preparation_state"],
                "VERIFIED_FOR_OFFLINE_PREPARATION",
            )
            self.assertEqual(
                ready.data["authorization_state"],
                "NOT_AUTHORIZED",
            )
            self.assert_no_provider_authority(ready.data)

            result = authorize(
                actor=self.ceo,
                project_id=self.project.pk,
                confirmed=True,
            )
            recorded = self.status_request(self.ceo)
            self.assertEqual(recorded.status_code, 200)
            self.assertTrue(recorded.data["preparation_ready"])
            self.assertEqual(
                recorded.data["authorization_state"],
                "DRAFT_INTENT_RECORDED",
            )
            self.assertEqual(
                recorded.data["intent_id"],
                result["evidence_id"],
            )
            self.assert_no_provider_authority(recorded.data)

    def test_source_retained_but_preparation_pending(self):
        self.ceo = User.objects.create_user(
            username="inspection_5208_ceo",
            role=Role.CEO,
            initials="CE",
        )
        inspection = self.capture()
        self.review(inspection)
        retain_installation_source(
            actor=self.inspector,
            project_id=self.project.pk,
            inspection_id=inspection.pk,
            content=b"%PDF-1.4\\n5208 retained evidence\\n%%EOF\\n",
            description="Disposable inspection source readiness acceptance.",
        )
        response = self.status_request(self.ceo)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["source_stage"],
            "SOURCE_VERIFIED_PREPARATION_PENDING",
        )
        self.assertFalse(response.data["preparation_ready"])
        self.assert_no_provider_authority(response.data)

    def test_comptroller_read_only_and_associate_denied(self):
        with patch.dict(os.environ, {
            "GECC_INSTALL_ATTESTATION_PREP_TEST_ENABLED": "1",
            "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED": "1",
        }):
            self.prepare_chain()
            before_events = AuditEvent.objects.count()
            before_evidence = ProjectEvidence.objects.count()

            comptroller = self.reviewer
            self.assertEqual(comptroller.role, Role.COMPTROLLER)
            response = self.status_request(comptroller)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.data["preparation_ready"])
            self.assert_no_provider_authority(response.data)

            associate = User.objects.create_user(
                username="inspection_5204_associate",
                role=Role.SALES_ASSOCIATE,
                initials="SA",
            )
            forbidden = self.status_request(associate)
            self.assertEqual(forbidden.status_code, 403)

            self.assertEqual(
                ProjectEvidence.objects.count(), before_evidence
            )
            self.assertEqual(
                AuditEvent.objects.count(), before_events
            )
            self.assertFalse(
                ProjectEvidence.objects.filter(
                    msr=self.msr, kind=KIND
                ).exists()
            )
