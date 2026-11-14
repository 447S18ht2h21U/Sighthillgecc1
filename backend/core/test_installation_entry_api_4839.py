"""Isolated API acceptance for Project Completion Review evidence entry."""
import os
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from .test_post_installation_acceptance_4819 import (
    PostInstallationAcceptance4819 as Fixture,
)
from .operational_project_api import OperationalProjectViewSet
from .post_installation_acceptance_4819 import INSPECTION_KIND, REVIEW_KIND
from .models import ProjectEvidence


@override_settings(DEBUG=True, ENVIRONMENT="development")
class InstallationEntryAPI4839(TestCase):
    setUp = Fixture.setUp

    def request(self, action, actor, payload):
        factory = APIRequestFactory()
        req = factory.post(
            f"/api/operational-projects/{self.project.pk}/{action}/",
            payload,
            format="json",
        )
        if actor is not None:
            force_authenticate(req, user=actor)
        view = OperationalProjectViewSet.as_view({
            "post": action.replace("-", "_"),
        })
        return view(req, pk=str(self.project.pk))

    def inspect(self, actor=None):
        return self.request(
            "record-installation-inspection",
            self.inspector if actor is None else actor,
            {
                "inspection_passed": True,
                "notes": "Physical inspection completed and documented.",
            },
        )

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {
            "GECC_INSTALLATION_EVIDENCE_BROWSER_ENABLED": "0"
        }):
            response = self.inspect()
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind=INSPECTION_KIND
            ).exists()
        )

    def test_role_boundary(self):
        with patch.dict(os.environ, {
            "GECC_INSTALLATION_EVIDENCE_BROWSER_ENABLED": "1"
        }):
            response = self.inspect(actor=self.reviewer)
        self.assertEqual(response.status_code, 403)

    def test_record_and_independent_review_never_grant_release(self):
        with patch.dict(os.environ, {
            "GECC_INSTALLATION_EVIDENCE_BROWSER_ENABLED": "1"
        }):
            recorded = self.inspect()
            self.assertEqual(recorded.status_code, 201, recorded.data)
            self.assertFalse(
                recorded.data["final_receipt_issuance_authorized"]
            )
            self.assertFalse(recorded.data["completion_authorized"])

            review = self.request(
                "review-installation-inspection",
                self.reviewer,
                {
                    "inspection_id": recorded.data["inspection_id"],
                    "accept": True,
                    "reason": "Independent examination supports candidate.",
                    "independently_examined": True,
                },
            )

        self.assertEqual(review.status_code, 201, review.data)
        self.assertEqual(
            review.data["status"], "INTERNAL_CANDIDATE_ACCEPTED"
        )
        self.assertFalse(review.data["source_authenticated"])
        self.assertFalse(review.data["trusted_installation_evidence"])
        self.assertFalse(review.data["completion_authorized"])
        self.assertEqual(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind=INSPECTION_KIND
            ).count(), 1
        )
        self.assertEqual(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind=REVIEW_KIND
            ).count(), 1
        )

    def test_duplicate_inspection_denied(self):
        with patch.dict(os.environ, {
            "GECC_INSTALLATION_EVIDENCE_BROWSER_ENABLED": "1"
        }):
            first = self.inspect()
            self.assertEqual(first.status_code, 201, first.data)
            second = self.inspect()
        self.assertEqual(second.status_code, 400)

    def test_generic_project_creation_stays_disallowed(self):
        factory = APIRequestFactory()
        request = factory.post(
            "/api/operational-projects/",
            {"state": "COMPLETED"},
            format="json",
        )
        force_authenticate(request, user=self.reviewer)

        view = OperationalProjectViewSet.as_view({
            "get": "list",
        })
        response = view(request)

        self.assertEqual(response.status_code, 405)
        self.assertFalse(
            ProjectEvidence.objects.filter(
                msr=self.msr, kind=INSPECTION_KIND
            ).exists()
        )

    def test_comptroller_cannot_record_inspection(self):
        with patch.dict(os.environ, {
            "GECC_INSTALLATION_EVIDENCE_BROWSER_ENABLED": "1"
        }):
            response = self.inspect(actor=self.reviewer)
        self.assertEqual(response.status_code, 403)
