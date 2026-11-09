"""Role-scope and no-invented-milestone attention regressions."""
from unittest.mock import patch
from django.test import SimpleTestCase

from .dashboard_attention import attention_hint, get_attention_projects


class FakeQuerySet:
    def __init__(self, projects):
        self.projects = projects

    def select_related(self, *names):
        return self

    def order_by(self, *names):
        return self

    def __iter__(self):
        return iter(self.projects)


class FakeProject:
    def __init__(self, state):
        self.state = state


class DashboardAttentionTests(SimpleTestCase):
    def test_only_scoped_projects_with_no_stages(self):
        pending = FakeProject("DRAFT")
        completed = FakeProject("APPROVED")
        user = object()
        with patch(
            "core.dashboard_attention.operational_project_scope",
            return_value=FakeQuerySet([pending, completed]),
        ) as scope, patch(
            "core.dashboard_attention.get_project_dashboard_stages",
            side_effect=[[], ["completed_customer_record"]],
        ) as stages:
            result = get_attention_projects(user)
        self.assertEqual(result, [pending])
        scope.assert_called_once_with(user)
        self.assertEqual(stages.call_count, 2)

    def test_empty_scope_returns_nothing(self):
        with patch(
            "core.dashboard_attention.operational_project_scope",
            return_value=FakeQuerySet([]),
        ):
            self.assertEqual(get_attention_projects(object()), [])

    def test_submitted_requires_review(self):
        self.assertIn("authorized reviewer", attention_hint("SUBMITTED")["detail"])

    def test_cancelled_does_not_authorize_work(self):
        self.assertIn("reopening", attention_hint("CANCELLED")["detail"])

    def test_draft_is_not_declared_completed(self):
        self.assertIn("draft", attention_hint("DRAFT")["label"].lower())

    def test_guidance_is_read_only(self):
        self.assertIs(attention_hint("APPROVED")["read_only"], True)

    def test_unknown_state_does_not_invent_milestone(self):
        result = attention_hint("UNKNOWN")
        self.assertIn("Confirm", result["detail"])

    def test_invalid_state_rejected(self):
        with self.assertRaises(ValueError):
            attention_hint(None)
