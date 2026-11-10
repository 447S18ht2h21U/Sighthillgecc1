from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .documents import canonical_hash
from .expedited_service_request_4565 import KIND as REQUEST_KIND
from .expedited_service_review_4565 import REVIEW_KIND
from .expedited_manager_decision_4565 import DECISION_KIND
from .models import ProjectEvidence
from .test_installation_schedule import InstallationScheduleTests


@override_settings(ENVIRONMENT="development", DEBUG=True)
class ExpeditedFullApi4566Tests(TestCase):
    setUp = InstallationScheduleTests.setUp
    make_installation_eligible = InstallationScheduleTests.make_installation_eligible

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_request_review_decision_and_start_remain_separate(self):
        self.make_installation_eligible()

        manager_client = self.client_for(self.manager)
        reviewer_client = self.client_for(self.comptroller)
        proposed = timezone.localdate() + timedelta(days=1)

        submitted = manager_client.post(
            reverse("installation-schedules-request-expedited"),
            {
                "project": str(self.project.pk),
                "proposed_date": proposed.isoformat(),
                "reason": (
                    "Fictional customer requests an earlier appointment "
                    "and will provide signed supporting documentation."
                ),
                "document_reference": "FICTIONAL-REQUEST-4566D",
            },
            format="json",
        )
        self.assertEqual(submitted.status_code, 201, submitted.data)
        self.assertIs(submitted.data["expedited_authorized"], False)

        request_id = submitted.data["evidence_id"]
        request_evidence = ProjectEvidence.objects.get(pk=request_id)
        self.assertEqual(request_evidence.kind, REQUEST_KIND)
        self.assertEqual(
            request_evidence.digest, canonical_hash(request_evidence.data)
        )

        reviewed = reviewer_client.post(
            reverse("installation-schedules-review-expedited"),
            {
                "request_id": request_id,
                "accept_candidate": True,
                "review_reason": (
                    "Independent review of the pending fictional request; "
                    "customer evidence has not been verified."
                ),
            },
            format="json",
        )
        self.assertEqual(reviewed.status_code, 201, reviewed.data)
        self.assertEqual(reviewed.data["status"], "CANDIDATE_ACCEPTED")
        self.assertIs(reviewed.data["installation_authorized"], False)

        decision_id = reviewed.data["decision_id"]
        review_evidence = ProjectEvidence.objects.get(pk=decision_id)
        self.assertEqual(review_evidence.kind, REVIEW_KIND)
        self.assertEqual(
            review_evidence.data["request_digest"], request_evidence.digest
        )

        decided = manager_client.post(
            reverse("installation-schedules-decide-expedited"),
            {
                "review_id": decision_id,
                "approve": True,
                "decision_reason": (
                    "Manager accepts the proposed date subject to "
                    "independent customer and cancellation verification."
                ),
            },
            format="json",
        )
        self.assertEqual(decided.status_code, 201, decided.data)
        self.assertEqual(
            decided.data["status"],
            "MANAGER_APPROVED_PENDING_CUSTOMER_EVIDENCE",
        )
        self.assertIs(decided.data["expedited_authorized"], False)

        manager_evidence = ProjectEvidence.objects.get(
            pk=decided.data["decision_id"]
        )
        self.assertEqual(manager_evidence.kind, DECISION_KIND)
        self.assertEqual(
            manager_evidence.data["review_digest"], review_evidence.digest
        )
        self.assertEqual(
            ProjectEvidence.objects.filter(
                msr=self.project.current_approved,
                kind__in=(REQUEST_KIND, REVIEW_KIND, DECISION_KIND),
            ).count(),
            3,
        )

        assessed = manager_client.post(
            reverse("installation-schedules-assess-start"),
            {
                "project": str(self.project.pk),
                "proposed_start": timezone.now().isoformat(),
            },
            format="json",
        )
        self.assertEqual(assessed.status_code, 200, assessed.data)
        self.assertIs(assessed.data["installation_authorized"], False)
        self.assertIs(assessed.data["installation_started"], False)
        self.assertIs(assessed.data["trusted_equipment_verified"], False)
        self.assertTrue(assessed.data["blockers"])

    def test_unprivileged_user_cannot_approve_manager_decision(self):
        self.make_installation_eligible()
        client = self.client_for(self.sales)
        response = client.post(
            reverse("installation-schedules-decide-expedited"),
            {
                "review_id": "11111111-1111-4111-8111-111111111111",
                "approve": True,
                "decision_reason": "Unauthorized fictional approval attempt.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            ProjectEvidence.objects.filter(kind=DECISION_KIND).exists()
        )