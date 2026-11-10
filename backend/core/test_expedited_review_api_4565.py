from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase, override_settings
from django.urls import resolve, reverse
from rest_framework.test import APIClient

from .models import Role, User


@override_settings(ENVIRONMENT="development", DEBUG=True)
class ExpeditedReviewApi4565Tests(TestCase):

    def setUp(self):
        self.url = reverse("installation-schedules-review-expedited")
        self.payload = {
            "request_id": str(uuid4()),
            "accept_candidate": True,
            "review_reason": "Independent review of fictional customer request.",
        }

    def test_named_route_resolves_correctly(self):
        self.assertEqual(
            resolve(self.url).func.actions["post"],
            "review_expedited_service",
        )

    def test_anonymous_request_denied_before_review_service(self):
        with patch(
            "core.expedited_service_review_4565.review_expedited_service_request"
        ) as service:
            response = APIClient().post(
                self.url, self.payload, format="json"
            )
        self.assertIn(response.status_code, (401, 403))
        service.assert_not_called()

    def test_authenticated_comptroller_reaches_review_service(self):
        reviewer = User.objects.create_user(
            username="fictional_expedited_reviewer",
            password="test-password",
            role=Role.COMPTROLLER,
            initials="CC",
        )
        client = APIClient()
        client.force_authenticate(user=reviewer)
        decision_id = uuid4()
        decision = SimpleNamespace(
            pk=decision_id,
            data={"status": "CANDIDATE_ACCEPTED"},
        )

        with patch(
            "core.expedited_service_review_4565.review_expedited_service_request",
            return_value=decision,
        ) as service:
            response = client.post(
                self.url, self.payload, format="json"
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["decision_id"], str(decision_id))
        self.assertIs(response.data["expedited_authorized"], False)
        self.assertIs(response.data["installation_authorized"], False)
        service.assert_called_once()
        self.assertEqual(
            service.call_args.kwargs["actor"].pk, reviewer.pk
        )

    def test_malformed_input_never_reaches_review_service(self):
        reviewer = User.objects.create_user(
            username="fictional_invalid_review_reviewer",
            password="test-password",
            role=Role.COMPTROLLER,
            initials="CC",
        )
        client = APIClient()
        client.force_authenticate(user=reviewer)

        with patch(
            "core.expedited_service_review_4565.review_expedited_service_request"
        ) as service:
            response = client.post(
                self.url,
                {
                    "request_id": "not-a-uuid",
                    "accept_candidate": True,
                    "review_reason": "short",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 400)
        service.assert_not_called()