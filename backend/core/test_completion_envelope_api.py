"""HTTP security tests for read-only completion-envelope inspection."""

from uuid import uuid4

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import CompletionEnvelopeAttempt
from . import test_completion_envelope_inspection as inspection_fixtures


@override_settings(DEBUG=True)
class CompletionEnvelopeAPITests(TestCase):
    setUp = inspection_fixtures.CompletionEnvelopeInspectionTests.setUp
    edit_submit = inspection_fixtures.CompletionEnvelopeInspectionTests.edit_submit
    approve = inspection_fixtures.CompletionEnvelopeInspectionTests.approve
    setup_review = inspection_fixtures.CompletionEnvelopeInspectionTests.setup_review
    setup_release = inspection_fixtures.CompletionEnvelopeInspectionTests.setup_release
    authorize_test_customer = inspection_fixtures.CompletionEnvelopeInspectionTests.authorize_test_customer
    approval = inspection_fixtures.CompletionEnvelopeInspectionTests.approval
    create_fixture_attempt = inspection_fixtures.CompletionEnvelopeInspectionTests.create_fixture_attempt
    def setUp(self):
        inspection_fixtures.CompletionEnvelopeInspectionTests.setUp(self)
        self.client = APIClient()

    def test_api_comptroller_can_inspect(self):
        attempt = self.create_fixture_attempt()
        self.client.force_authenticate(user=self.comptroller)
        response = self.client.get(
            f"/api/completion-envelope-attempts/{attempt.pk}/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["attempt_id"], str(attempt.pk))
        self.assertFalse(response.data["provider_authenticated"])
        self.assertFalse(response.data["signature_completion_verified"])
        self.assertFalse(response.data["send_available"])
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_api_inactive_comptroller_is_forbidden(self):
        attempt = self.create_fixture_attempt()
        self.comptroller.is_active = False
        self.client.force_authenticate(user=self.comptroller)
        response = self.client.get(
            f"/api/completion-envelope-attempts/{attempt.pk}/"
        )
        self.assertEqual(response.status_code, 403)

    def test_api_forbidden_response_disables_caching(self):
        attempt = self.create_fixture_attempt()
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(f"/api/completion-envelope-attempts/{attempt.pk}/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get("Cache-Control"), "private, no-store")
        self.assertEqual(response.get("Referrer-Policy"), "no-referrer")
        self.assertEqual(response.get("X-Content-Type-Options"), "nosniff")
    def test_api_forbidden_response_does_not_disclose_attempt(self):
        attempt = self.create_fixture_attempt()
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(f"/api/completion-envelope-attempts/{attempt.pk}/")
        self.assertEqual(response.status_code, 403)
        body = response.content.decode("utf-8")
        self.assertNotIn(str(attempt.pk), body)
        self.assertNotIn(attempt.provider_account_id, body)
        self.assertNotIn(attempt.release_package.digest, body)
        self.assertNotIn(str(attempt.release_package_id), body)
    def test_api_manager_is_forbidden(self):
        attempt = self.create_fixture_attempt()
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(
            f"/api/completion-envelope-attempts/{attempt.pk}/"
        )
        self.assertEqual(response.status_code, 403)

    def test_api_anonymous_access_is_denied(self):
        attempt = self.create_fixture_attempt()
        response = self.client.get(
            f"/api/completion-envelope-attempts/{attempt.pk}/"
        )
        self.assertIn(response.status_code, (401, 403))

    def test_api_unknown_attempt_returns_404(self):
        self.create_fixture_attempt()
        self.client.force_authenticate(user=self.comptroller)
        response = self.client.get(
            f"/api/completion-envelope-attempts/{uuid4()}/"
        )
        self.assertEqual(response.status_code, 404)

    def test_api_post_is_not_allowed(self):
        attempt = self.create_fixture_attempt()
        self.client.force_authenticate(user=self.comptroller)
        response = self.client.post(
            f"/api/completion-envelope-attempts/{attempt.pk}/", {}
        )
        self.assertEqual(response.status_code, 405)
