"""Isolated default-deny tests for proposed MSR delegation drafts."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.test import SimpleTestCase

from .access_msr_delegation_drafts import (
    msr_delegation_draft_grants_access,
    msr_delegation_draft_grants_financial_access,
    msr_delegation_draft_grants_signing,
    msr_delegation_draft_grants_write,
    validate_msr_delegation_draft,
)
from .models import Role


class MSRDelegationDraftTests(SimpleTestCase):
    def setUp(self):
        self.manager = uuid4()
        self.recipient = uuid4()
        self.source = uuid4()
        self.project = uuid4()
        self.now = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)

    def values(self, **changes):
        values = {
            "manager_id": self.manager,
            "manager_role": Role.SALES_MANAGER,
            "manager_active": True,
            "recipient_id": self.recipient,
            "recipient_role": Role.SALES_ASSOCIATE,
            "recipient_active": True,
            "source_associate_id": self.source,
            "source_associate_role": Role.SALES_ASSOCIATE,
            "source_associate_active": True,
            "project_ids": (self.project,),
            "starts_at": self.now,
            "ends_at": self.now + timedelta(days=2),
            "reason": "Approved vacation coverage request.",
        }
        values.update(changes)
        return values

    def test_valid_fixed_project_draft(self):
        draft = validate_msr_delegation_draft(**self.values())
        self.assertEqual(draft.project_ids, (self.project,))
        self.assertTrue(draft.read_only)

    def test_inactive_manager_denied(self):
        with self.assertRaises(ValueError):
            validate_msr_delegation_draft(
                **self.values(manager_active=False)
            )

    def test_unauthorized_manager_role_denied(self):
        with self.assertRaises(ValueError):
            validate_msr_delegation_draft(
                **self.values(manager_role=Role.COMPTROLLER)
            )

    def test_non_sales_recipient_denied(self):
        with self.assertRaises(ValueError):
            validate_msr_delegation_draft(
                **self.values(recipient_role=Role.TECHNICIAN)
            )

    def test_inactive_recipient_denied(self):
        with self.assertRaises(ValueError):
            validate_msr_delegation_draft(
                **self.values(recipient_active=False)
            )

    def test_source_must_be_sales_associate(self):
        with self.assertRaises(ValueError):
            validate_msr_delegation_draft(
                **self.values(source_associate_role=Role.TECHNICIAN)
            )

    def test_source_account_may_be_inactive_for_coverage(self):
        draft = validate_msr_delegation_draft(
            **self.values(source_associate_active=False)
        )
        self.assertEqual(draft.source_associate_id, self.source)

    def test_self_and_duplicate_participants_denied(self):
        for changes in (
            {"manager_id": self.recipient},
            {"source_associate_id": self.recipient},
            {"source_associate_id": self.manager},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    validate_msr_delegation_draft(
                        **self.values(**changes)
                    )

    def test_empty_and_duplicate_project_scope_denied(self):
        for projects in (
            (),
            (self.project, self.project),
            ("not-a-uuid",),
        ):
            with self.subTest(projects=projects):
                with self.assertRaises(ValueError):
                    validate_msr_delegation_draft(
                        **self.values(project_ids=projects)
                    )

    def test_invalid_time_windows_denied(self):
        for changes in (
            {"ends_at": self.now},
            {"ends_at": self.now - timedelta(seconds=1)},
            {"starts_at": self.now.replace(tzinfo=None)},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    validate_msr_delegation_draft(
                        **self.values(**changes)
                    )

    def test_missing_justification_denied(self):
        with self.assertRaises(ValueError):
            validate_msr_delegation_draft(
                **self.values(reason="short")
            )

    def test_no_operational_or_sensitive_access(self):
        draft = validate_msr_delegation_draft(**self.values())
        self.assertFalse(msr_delegation_draft_grants_access(draft))
        self.assertFalse(msr_delegation_draft_grants_write(draft))
        self.assertFalse(msr_delegation_draft_grants_signing(draft))
        self.assertFalse(msr_delegation_draft_grants_financial_access(draft))