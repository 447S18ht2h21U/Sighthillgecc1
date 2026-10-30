"""Database-free tests for individual permission request drafts."""

import uuid
from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from .access_user_permission_request_drafts import (
    request_draft_grants_access,
    validate_user_permission_request_draft,
)


class IndividualPermissionRequestDraftTests(SimpleTestCase):
    def setUp(self):
        self.start = datetime(2026, 11, 1, tzinfo=timezone.utc)
        self.data = dict(
            recipient_id=uuid.uuid4(),
            requester_id=uuid.uuid4(),
            permission_code="customers.view",
            scope="ASSIGNED_PROJECTS",
            starts_at=self.start,
            ends_at=self.start + timedelta(days=30),
            reason="Required for assigned customer projects.",
        )

    def test_request_is_bound_to_individual_user(self):
        draft = validate_user_permission_request_draft(**self.data)
        self.assertEqual(draft.recipient_id, self.data["recipient_id"])
        self.assertEqual(draft.requester_id, self.data["requester_id"])
        self.assertFalse(request_draft_grants_access(draft))

    def test_distinct_users_can_have_distinct_proposals(self):
        first = validate_user_permission_request_draft(**self.data)
        second = validate_user_permission_request_draft(
            **{**self.data, "recipient_id": uuid.uuid4()}
        )
        self.assertNotEqual(first.recipient_id, second.recipient_id)

    def test_all_project_scope_requires_independent_review(self):
        draft = validate_user_permission_request_draft(
            **{**self.data, "scope": "ALL_PROJECTS"}
        )
        self.assertTrue(draft.requires_independent_approval)

    def test_specific_projects_are_preserved(self):
        project = uuid.uuid4()
        draft = validate_user_permission_request_draft(
            **{
                **self.data,
                "scope": "SPECIFIC_PROJECTS",
                "project_ids": [str(project)],
            }
        )
        self.assertEqual(draft.project_ids, (project,))

    def test_invalid_identity_rejected(self):
        for value in ("not-a-uuid", None, 123):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_user_permission_request_draft(
                        **{**self.data, "recipient_id": value}
                    )

    def test_missing_reason_rejected(self):
        with self.assertRaises(ValueError):
            validate_user_permission_request_draft(
                **{**self.data, "reason": " "}
            )

    def test_naive_dates_rejected(self):
        with self.assertRaises(ValueError):
            validate_user_permission_request_draft(
                **{
                    **self.data,
                    "starts_at": datetime(2026, 11, 1),
                }
            )

    def test_reversed_period_rejected(self):
        with self.assertRaises(ValueError):
            validate_user_permission_request_draft(
                **{
                    **self.data,
                    "ends_at": self.start - timedelta(days=1),
                }
            )

    def test_unknown_permission_rejected(self):
        with self.assertRaises(ValueError):
            validate_user_permission_request_draft(
                **{
                    **self.data,
                    "permission_code": "system.superuser",
                }
            )

    def test_unscoped_financial_request_needs_review(self):
        draft = validate_user_permission_request_draft(
            **{
                **self.data,
                "permission_code": "financials.cashflow.view",
                "scope": "NOT_APPLICABLE",
            }
        )
        self.assertTrue(draft.requires_independent_approval)
        self.assertFalse(request_draft_grants_access(draft))

    def test_self_request_is_not_self_approval(self):
        draft = validate_user_permission_request_draft(
            **{
                **self.data,
                "requester_id": self.data["recipient_id"],
            }
        )
        self.assertFalse(request_draft_grants_access(draft))