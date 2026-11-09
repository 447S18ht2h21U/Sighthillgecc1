"""Approved delegation evidence cannot expand live MSR HTTP access.

Runs only with disposable Django test records. No production routes added.
"""

import time
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from .models import AuditHead, Role, User
from .test_visible_msr_api import VisibleMSRAPITests
from .msr_delegation_request_service import create_fixed_msr_delegation_request
from .msr_delegation_approval_service import approve_fixed_msr_delegation
from .msr_delegation_termination_service import terminate_fixed_msr_delegation


@override_settings(ROOT_URLCONF="config.urls")
class ApprovedDelegationVisibilityIsolationTests(TestCase):
    def setUp(self):
        VisibleMSRAPITests.setUp(self)
        self.sales_manager = User.objects.create_user(
            username="visibility_delegation_manager_3895",
            role=Role.SALES_MANAGER,
            initials="VM",
        )
        AuditHead.objects.get_or_create(pk=1)

    def sign_in(self, actor):
        self.client.logout()
        self.client.force_login(actor)
        session = self.client.session
        session["last_activity"] = time.time()
        session.save()

    def visible_ids(self):
        response = self.client.get("/api/visible-msrs/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        records = data["results"] if isinstance(data, dict) and "results" in data else data
        return {str(item["id"]) for item in records}

    def request_coverage(self):
        now = timezone.now()
        return create_fixed_msr_delegation_request(
            manager_id=self.sales_manager.pk,
            recipient_id=self.sales.pk,
            source_associate_id=self.other_sales.pk,
            project_ids=[self.other_project.pk],
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(hours=1),
            reason="Temporary coverage for another sales associate",
        )

    def approve_coverage(self, request):
        return approve_fixed_msr_delegation(
            request_id=request.pk,
            approver_id=self.comptroller.pk,
            reason="Independent approval for temporary project coverage",
        )

    def assert_recipient_scope_unchanged(self):
        self.sign_in(self.sales)
        ids = self.visible_ids()
        self.assertEqual(ids, {str(self.msr.pk)})
        self.assertNotIn(str(self.other_msr.pk), ids)

        response = self.client.get(
            f"/api/visible-msrs/{self.other_msr.pk}/"
        )
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(b"Other project", response.content)

    def test_before_approval_recipient_cannot_view_other_msr(self):
        self.request_coverage()
        self.assert_recipient_scope_unchanged()

    def test_after_approval_recipient_still_cannot_view_other_msr(self):
        request = self.request_coverage()
        decision = self.approve_coverage(request)
        self.assertEqual(decision.result, "APPROVED")
        self.assert_recipient_scope_unchanged()

    def test_after_termination_recipient_still_cannot_view_other_msr(self):
        request = self.request_coverage()
        decision = self.approve_coverage(request)
        event = terminate_fixed_msr_delegation(
            decision_id=decision.pk,
            actor_id=self.sales.pk,
            kind="VOLUNTARY_SURRENDER",
            reason="Recipient ended temporary coverage voluntarily",
        )
        self.assertEqual(event.decision_id, decision.pk)
        self.assert_recipient_scope_unchanged()

    def test_approval_does_not_remove_source_owner_access(self):
        request = self.request_coverage()
        self.approve_coverage(request)
        self.sign_in(self.other_sales)
        self.assertIn(str(self.other_msr.pk), self.visible_ids())
        self.assertNotIn(str(self.msr.pk), self.visible_ids())

    def test_approval_does_not_change_comptroller_access(self):
        request = self.request_coverage()
        self.approve_coverage(request)
        self.sign_in(self.comptroller)
        self.assertEqual(
            self.visible_ids(),
            {str(self.msr.pk), str(self.other_msr.pk)},
        )