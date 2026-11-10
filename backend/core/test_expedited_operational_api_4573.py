"""Isolated API verification; never grants expedited authority."""
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from .operational_project_api import OperationalProjectViewSet
from .expedited_observation_storage_4569 import (
    retain_unverified_expedited_observation,
)
from .test_expedited_observation_storage_4569 import (
    ExpeditedObservationStorage4569Tests,
)


@override_settings(ENVIRONMENT="development", DEBUG=True)
class ExpeditedOperationalAPI4573Tests(TestCase):
    def setUp(self):
        ExpeditedObservationStorage4569Tests.setUp(self)
        self.factory = APIRequestFactory()
        self.view = OperationalProjectViewSet.as_view({
            "get": "installation_eligibility",
        })

    def get_status(self, actor=None):
        request = self.factory.get(
            "/api/operational-projects/"
            f"{self.msr.project_id}/installation-eligibility/"
        )
        if actor is not None:
            force_authenticate(request, user=actor)
        return self.view(request, pk=str(self.msr.project_id))

    def test_attempt_is_visible_but_not_authorized(self):
        response = self.get_status(self.manager)
        self.assertEqual(response.status_code, 200)

        expedited = response.data["expedited_service"]
        self.assertTrue(expedited["attempt_recorded"])
        self.assertFalse(expedited["documents_retained"])
        self.assertFalse(expedited["installation_authorized"])
        self.assertFalse(expedited["expedited_authorized"])

    def test_retained_documents_never_grant_authority(self):
        before = self.get_status(self.manager)
        self.assertEqual(before.status_code, 200)
        original_eligibility = before.data["eligible"]

        retain_unverified_expedited_observation(
            actor=self.manager,
            binding_id=self.binding_id,
            candidate=self.candidate,
            pdf_bytes=self.pdfs,
        )

        response = self.get_status(self.manager)
        self.assertEqual(response.status_code, 200)

        expedited = response.data["expedited_service"]
        self.assertTrue(expedited["documents_retained"])
        self.assertEqual(expedited["retained_document_count"], 3)
        self.assertFalse(expedited["provider_authenticated"])
        self.assertFalse(expedited["signatures_verified"])
        self.assertFalse(expedited["distribution_verified"])
        self.assertFalse(expedited["installation_authorized"])
        self.assertEqual(response.data["eligible"], original_eligibility)

    def test_unauthenticated_project_request_denied(self):
        response = self.get_status()
        self.assertIn(response.status_code, (401, 403, 404))
        self.assertNotIn("expedited_service", response.data)
