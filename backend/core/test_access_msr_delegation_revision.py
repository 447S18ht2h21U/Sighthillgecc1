"""Isolated ownership-revision security checks."""

import unittest
from uuid import uuid4

from core.access_msr_delegation_revision import (
    MAX_REVISION,
    make_ownership_snapshot,
    ownership_matches,
    valid_reassignment,
    ownership_revision_grants_msr_access,
)


class OwnershipRevisionTests(unittest.TestCase):
    def setUp(self):
        self.project = uuid4()
        self.first = uuid4()
        self.second = uuid4()

    def snap(self, owner, revision=0):
        return make_ownership_snapshot(
            project_id=self.project, owner_id=owner, revision=revision
        )

    def test_valid_snapshot(self):
        self.assertIsNotNone(self.snap(self.first))

    def test_matching_current_owner(self):
        self.assertTrue(ownership_matches(
            self.snap(self.first),
            project_id=self.project,
            owner_id=self.first,
            revision=0,
        ))

    def test_other_owner_denied(self):
        self.assertFalse(ownership_matches(
            self.snap(self.first),
            project_id=self.project,
            owner_id=self.second,
            revision=0,
        ))

    def test_different_project_denied(self):
        self.assertFalse(ownership_matches(
            self.snap(self.first),
            project_id=uuid4(),
            owner_id=self.first,
            revision=0,
        ))

    def test_stale_revision_denied(self):
        self.assertFalse(ownership_matches(
            self.snap(self.first),
            project_id=self.project,
            owner_id=self.first,
            revision=2,
        ))

    def test_reassignment_valid(self):
        self.assertTrue(valid_reassignment(
            self.snap(self.first, 0), self.snap(self.second, 1)
        ))

    def test_return_increments_revision(self):
        old = self.snap(self.first, 0)
        changed = self.snap(self.second, 1)
        returned = self.snap(self.first, 2)
        self.assertTrue(valid_reassignment(old, changed))
        self.assertTrue(valid_reassignment(changed, returned))
        self.assertFalse(ownership_matches(
            old, project_id=self.project,
            owner_id=self.first, revision=2,
        ))

    def test_revision_skip_denied(self):
        self.assertFalse(valid_reassignment(
            self.snap(self.first, 0), self.snap(self.second, 2)
        ))

    def test_unchanged_owner_denied_as_reassignment(self):
        self.assertFalse(valid_reassignment(
            self.snap(self.first, 0), self.snap(self.first, 1)
        ))

    def test_cross_project_reassignment_denied(self):
        other = make_ownership_snapshot(
            project_id=uuid4(), owner_id=self.second, revision=1
        )
        self.assertFalse(valid_reassignment(self.snap(self.first), other))

    def test_invalid_revision_inputs_denied(self):
        for value in (-1, True, 1.5, "1", MAX_REVISION + 1):
            self.assertIsNone(make_ownership_snapshot(
                project_id=self.project, owner_id=self.first,
                revision=value,
            ))

    def test_invalid_identity_denied(self):
        self.assertIsNone(make_ownership_snapshot(
            project_id="invalid", owner_id=self.first, revision=0
        ))

    def test_untrusted_snapshot_denied(self):
        self.assertFalse(ownership_matches(
            {"project_id": self.project, "owner_id": self.first,
             "revision": 0},
            project_id=self.project, owner_id=self.first, revision=0,
        ))

    def test_revision_overflow_denied(self):
        self.assertFalse(valid_reassignment(
            self.snap(self.first, MAX_REVISION),
            self.snap(self.second, MAX_REVISION),
        ))

    def test_no_live_access(self):
        self.assertFalse(ownership_revision_grants_msr_access())


if __name__ == "__main__":
    unittest.main()