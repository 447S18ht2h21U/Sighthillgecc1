import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from core.models import Role
from core.msr_delegation_approval_service import (
    validate_locked_approval_evidence,
    approval_service_grants_live_msr_access,
)


class AtomicApprovalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
        self.manager, self.recipient, self.source, self.approver = [
            uuid4() for _ in range(4)
        ]
        self.request_id = uuid4()
        self.project_id = uuid4()
        self.request = SimpleNamespace(
            pk=self.request_id,
            manager_id=self.manager,
            recipient_id=self.recipient,
            source_associate_id=self.source,
            starts_at=self.now - timedelta(hours=1),
            ends_at=self.now + timedelta(hours=1),
            read_only=True,
            reason="Temporary sales coverage requested",
        )
        self.scopes = [
            SimpleNamespace(
                request_id=self.request_id,
                project_id=self.project_id,
                owner_revision=0,
            )
        ]
        self.projects = {
            self.project_id: SimpleNamespace(
                sales_associate_id=self.source,
                ownership_revision=0,
            )
        }
        self.users = {
            self.manager: SimpleNamespace(
                role=Role.SALES_MANAGER, is_active=True
            ),
            self.recipient: SimpleNamespace(
                role=Role.SALES_ASSOCIATE, is_active=True
            ),
            self.source: SimpleNamespace(
                role=Role.SALES_ASSOCIATE, is_active=False
            ),
            self.approver: SimpleNamespace(
                role=Role.COMPTROLLER, is_active=True
            ),
        }

    def valid(self):
        return validate_locked_approval_evidence(
            self.request, self.scopes, self.projects, self.users,
            self.approver, self.now,
        )

    def test_independent_comptroller_can_approve(self):
        self.assertTrue(self.valid())

    def test_independent_ceo_can_approve(self):
        self.users[self.approver].role = Role.CEO
        self.assertTrue(self.valid())

    def test_manager_cannot_approve(self):
        self.users[self.approver].role = Role.SALES_MANAGER
        self.assertFalse(self.valid())

    def test_self_approval_denied(self):
        self.request.manager_id = self.approver
        self.assertFalse(self.valid())

    def test_recipient_is_approver_denied(self):
        self.request.recipient_id = self.approver
        self.assertFalse(self.valid())

    def test_inactive_approver_denied(self):
        self.users[self.approver].is_active = False
        self.assertFalse(self.valid())

    def test_inactive_recipient_denied(self):
        self.users[self.recipient].is_active = False
        self.assertFalse(self.valid())

    def test_inactive_manager_denied(self):
        self.users[self.manager].is_active = False
        self.assertFalse(self.valid())

    def test_source_may_be_inactive(self):
        self.assertTrue(self.valid())

    def test_reassigned_project_denied(self):
        self.projects[self.project_id].sales_associate_id = uuid4()
        self.assertFalse(self.valid())

    def test_stale_revision_denied(self):
        self.projects[self.project_id].ownership_revision = 1
        self.assertFalse(self.valid())

    def test_returned_owner_still_denied(self):
        self.projects[self.project_id].ownership_revision = 2
        self.assertFalse(self.valid())

    def test_scope_missing_project_denied(self):
        self.projects.clear()
        self.assertFalse(self.valid())

    def test_extra_project_denied(self):
        self.projects[uuid4()] = SimpleNamespace(
            sales_associate_id=self.source, ownership_revision=0
        )
        self.assertFalse(self.valid())

    def test_expired_request_denied(self):
        self.request.ends_at = self.now
        self.assertFalse(self.valid())

    def test_read_only_required(self):
        self.request.read_only = False
        self.assertFalse(self.valid())

    def test_no_live_access(self):
        self.assertFalse(approval_service_grants_live_msr_access())


if __name__ == "__main__":
    unittest.main()