"""Isolated tests for proposed project permission scopes."""

import uuid

from django.test import SimpleTestCase

from .access_permission_scope_drafts import (
    scope_draft_grants_access,
    validate_permission_scope_draft,
)


class PermissionScopeDraftTests(SimpleTestCase):

    def test_assigned_project_scope(self):
        draft = validate_permission_scope_draft(
            "dashboard.view", "ASSIGNED_PROJECTS"
        )
        self.assertEqual(draft.scope, "ASSIGNED_PROJECTS")
        self.assertFalse(draft.requires_independent_approval)

    def test_specific_project_scope(self):
        project = uuid.uuid4()
        draft = validate_permission_scope_draft(
            "customers.view", "SPECIFIC_PROJECTS", [project]
        )
        self.assertEqual(draft.project_ids, (project,))
        self.assertFalse(scope_draft_grants_access(draft, project))

    def test_all_projects_requires_review(self):
        draft = validate_permission_scope_draft(
            "customers.view", "ALL_PROJECTS"
        )
        self.assertTrue(draft.requires_independent_approval)

    def test_unscoped_permission(self):
        draft = validate_permission_scope_draft(
            "financials.operations.view", "NOT_APPLICABLE"
        )
        self.assertTrue(draft.requires_independent_approval)

    def test_unknown_permission_denied(self):
        with self.assertRaises(ValueError):
            validate_permission_scope_draft(
                "system.unrestricted", "ALL_PROJECTS"
            )

    def test_unknown_scope_denied(self):
        with self.assertRaises(ValueError):
            validate_permission_scope_draft(
                "customers.view", "ANYTHING"
            )

    def test_specific_projects_requires_ids(self):
        with self.assertRaises(ValueError):
            validate_permission_scope_draft(
                "customers.view", "SPECIFIC_PROJECTS", []
            )

    def test_project_ids_not_allowed_for_assigned_scope(self):
        with self.assertRaises(ValueError):
            validate_permission_scope_draft(
                "customers.view",
                "ASSIGNED_PROJECTS",
                [uuid.uuid4()],
            )

    def test_unscoped_permission_rejects_project_scope(self):
        with self.assertRaises(ValueError):
            validate_permission_scope_draft(
                "financials.operations.view", "ALL_PROJECTS"
            )

    def test_duplicate_project_ids_rejected(self):
        project = uuid.uuid4()
        with self.assertRaises(ValueError):
            validate_permission_scope_draft(
                "customers.view",
                "SPECIFIC_PROJECTS",
                [project, str(project)],
            )

    def test_invalid_project_id_rejected(self):
        with self.assertRaises(ValueError):
            validate_permission_scope_draft(
                "customers.view",
                "SPECIFIC_PROJECTS",
                ["invalid-identifier"],
            )

    def test_proposals_never_grant_access(self):
        draft = validate_permission_scope_draft(
            "customers.manage", "ALL_PROJECTS"
        )
        self.assertFalse(scope_draft_grants_access(draft))