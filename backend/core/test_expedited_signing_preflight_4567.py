from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .documents import canonical_hash
from .models import Role
from .expedited_signing_preflight_4567 import (
    assess_unified_signing_preflight,
    REQUEST_KIND, REVIEW_KIND, DECISION_KIND,
)

MODULE = "core.expedited_signing_preflight_4567"


@override_settings(ENVIRONMENT="development", DEBUG=True)
class UnifiedSigningPreflight4567Tests(SimpleTestCase):
    def setUp(self):
        self.project_id = uuid4()
        self.msr_id = uuid4()
        self.actor_id = uuid4()
        self.actor = SimpleNamespace(pk=self.actor_id)
        self.user = SimpleNamespace(
            pk=self.actor_id, is_active=True, role=Role.COMPTROLLER,
        )
        self.msr = SimpleNamespace(
            pk=self.msr_id, status="APPROVED",
            project_id=self.project_id, number=3,
            snapshot={"fictional_customer": "FICTIONAL"},
        )
        self.project = SimpleNamespace(
            pk=self.project_id, state="ACTIVE",
            current_approved=self.msr,
            current_approved_id=self.msr_id,
        )
        self.requester_id = uuid4()
        self.reviewer_id = uuid4()
        self.manager_id = uuid4()
        self.records = []

    def make_records(self):
        request_id, review_id, decision_id = uuid4(), uuid4(), uuid4()
        common = {
            "project_id": str(self.project_id),
            "msr_id": str(self.msr_id),
            "msr_version": 3,
            "snapshot_sha256": canonical_hash(self.msr.snapshot),
            "proposed_date": "2026-11-15",
        }
        request = {
            **common,
            "status": "PENDING_INDEPENDENT_VERIFICATION",
            "requested_by": str(self.requester_id),
        }
        request_hash = canonical_hash(request)
        review = {
            **common,
            "status": "CANDIDATE_ACCEPTED",
            "request_id": str(request_id),
            "request_digest": request_hash,
            "reviewer_id": str(self.reviewer_id),
        }
        review_hash = canonical_hash(review)
        decision = {
            **common,
            "status": "MANAGER_APPROVED_PENDING_CUSTOMER_EVIDENCE",
            "request_id": str(request_id),
            "request_digest": request_hash,
            "review_id": str(review_id),
            "review_digest": review_hash,
        }
        self.records = [
            SimpleNamespace(
                pk=request_id, kind=REQUEST_KIND,
                msr_id=self.msr_id,
                created_by_id=self.requester_id,
                data=request, digest=request_hash,
            ),
            SimpleNamespace(
                pk=review_id, kind=REVIEW_KIND,
                msr_id=self.msr_id,
                created_by_id=self.reviewer_id,
                data=review, digest=review_hash,
            ),
            SimpleNamespace(
                pk=decision_id, kind=DECISION_KIND,
                msr_id=self.msr_id,
                created_by_id=self.manager_id,
                data=decision, digest=canonical_hash(decision),
            ),
        ]

    def assess(self, *, chain_ok=True):
        if not self.records:
            self.make_records()

        with (
            patch(f"{MODULE}.User.objects.filter") as users,
            patch(f"{MODULE}.Project.objects.select_related") as projects,
            patch(f"{MODULE}.ProjectEvidence.objects.filter") as evidence,
            patch(
                f"{MODULE}.assess_expedited_chain",
                return_value={"expedited_chain_reviewed": chain_ok},
            ),
        ):
            users.return_value.first.return_value = self.user
            projects.return_value.filter.return_value.first.return_value = (
                self.project
            )
            evidence.return_value = self.records
            return assess_unified_signing_preflight(
                actor=self.actor, project_id=str(self.project_id),
            )

    def test_valid_chain_reports_readiness_without_authority(self):
        result = self.assess()
        self.assertEqual(result["msr_id"], str(self.msr_id))
        self.assertEqual(result["envelope_count"], 1)
        self.assertEqual(result["proposed_date"], "2026-11-15")
        self.assertTrue(result["administrative_chain_reviewed"])
        self.assertFalse(result["send_authorized"])
        self.assertFalse(result["customer_signatures_verified"])
        self.assertFalse(result["installation_authorized"])

    def test_incomplete_chain_rejected(self):
        with self.assertRaises(ValidationError):
            self.assess(chain_ok=False)

    def test_mismatched_date_rejected(self):
        self.make_records()
        self.records[2].data["proposed_date"] = "2026-11-16"
        self.records[2].digest = canonical_hash(self.records[2].data)
        with self.assertRaises(ValidationError):
            self.assess()

    def test_tampered_record_rejected(self):
        self.make_records()
        self.records[1].data["status"] = "REJECTED"
        with self.assertRaises(ValidationError):
            self.assess()

    def test_duplicate_record_rejected(self):
        self.make_records()
        self.records.append(self.records[0])
        with self.assertRaises(ValidationError):
            self.assess()

    def test_same_requester_and_reviewer_rejected(self):
        self.make_records()
        self.records[1].created_by_id = self.requester_id
        with self.assertRaises(ValidationError):
            self.assess()

    def test_superseded_msr_rejected(self):
        self.project.current_approved_id = uuid4()
        with self.assertRaises(ValidationError):
            self.assess()

    def test_inactive_actor_rejected(self):
        self.user.is_active = False
        with self.assertRaises(PermissionDenied):
            self.assess()

    def test_wrong_role_rejected(self):
        self.user.role = Role.SALES_ASSOCIATE
        with self.assertRaises(PermissionDenied):
            self.assess()

    @override_settings(ENVIRONMENT="production", DEBUG=False)
    def test_production_disabled(self):
        with self.assertRaises(PermissionDenied):
            assess_unified_signing_preflight(
                actor=self.actor, project_id=str(self.project_id),
            )

    def test_snapshot_binding_mismatch_rejected(self):
        self.make_records()
        self.msr.snapshot = {"fictional_customer": "CHANGED"}
        with self.assertRaises(ValidationError):
            self.assess()

    def test_missing_evidence_rejected(self):
        self.make_records()
        self.records.pop()
        with self.assertRaises(ValidationError):
            self.assess()
