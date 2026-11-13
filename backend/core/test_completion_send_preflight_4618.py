"""Focused unit checks for completion send authorization."""
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Role
from .completion_send_preflight_4618 import (
    require_completion_send_preflight,
)


class CompletionSendPreflightTests(SimpleTestCase):
    def setUp(self):
        self.actor = SimpleNamespace(
            pk=uuid4(),
            is_authenticated=True,
            is_active=True,
            role=Role.SALES_MANAGER,
        )
        self.initiator = SimpleNamespace(
            pk=uuid4(),
            is_active=True,
            role=Role.COMPTROLLER,
        )
        msr_id = uuid4()
        project_id = uuid4()
        self.project = SimpleNamespace(
            pk=project_id,
            current_approved_id=msr_id,
            state="ACTIVE",
        )
        self.msr = SimpleNamespace(
            pk=msr_id,
            project_id=project_id,
            project=self.project,
            status="APPROVED",
            snapshot={"financing_type": "FINANCED"},
        )
        self.plan = SimpleNamespace(
            msr=self.msr,
            msr_id=msr_id,
            group="COMPLETION_FINANCED",
        )
        package_id = uuid4()
        self.package = SimpleNamespace(
            pk=package_id,
            plan=self.plan,
        )
        self.attempt = SimpleNamespace(
            pk=uuid4(),
            release_package_id=package_id,
            release_package=self.package,
            initiated_by=self.initiator,
            provider_account_id=str(uuid4()),
            provider_envelope_id="",
            first_send_started_at=None,
            state="AUTH_PENDING",
        )

    def assess(self, status="APPROVED"):
        with patch(
            "core.release.validate_package"
        ) as validate, patch(
            "core.release.status",
            return_value={"status": status},
        ):
            result = require_completion_send_preflight(
                actor=self.actor,
                attempt=self.attempt,
            )
            validate.assert_called_once_with(
                self.package, check_current=True
            )
            return result

    def test_sales_manager_can_pass_read_only_gate(self):
        result = self.assess()
        self.assertTrue(result.authority_validated)
        self.assertTrue(result.release_validated)
        self.assertFalse(result.live_sending_enabled)
        self.assertFalse(result.envelope_sent)
        self.assertFalse(result.completion_authorized)

    def test_ceo_can_pass_read_only_gate(self):
        self.actor.role = Role.CEO
        self.assertTrue(self.assess().authority_validated)

    def test_comptroller_cannot_send(self):
        self.actor.role = Role.COMPTROLLER
        with self.assertRaises(PermissionDenied):
            self.assess()

    def test_installation_manager_cannot_send(self):
        self.actor.role = Role.INSTALLATION_MANAGER
        with self.assertRaises(PermissionDenied):
            self.assess()

    def test_sales_associate_cannot_send(self):
        self.actor.role = Role.SALES_ASSOCIATE
        with self.assertRaises(PermissionDenied):
            self.assess()

    def test_inactive_manager_cannot_send(self):
        self.actor.is_active = False
        with self.assertRaises(PermissionDenied):
            self.assess()

    def test_current_msr_binding_required(self):
        self.project.current_approved_id = uuid4()
        with self.assertRaises(ValidationError):
            self.assess()

    def test_financing_group_must_match(self):
        self.plan.group = "COMPLETION_NON_FINANCED"
        with self.assertRaises(ValidationError):
            self.assess()

    def test_attempt_must_be_unsent(self):
        self.attempt.state = "SENT_UNCHECKED"
        with self.assertRaises(ValidationError):
            self.assess()

    def test_provider_envelope_must_be_empty(self):
        self.attempt.provider_envelope_id = str(uuid4())
        with self.assertRaises(ValidationError):
            self.assess()

    def test_comptroller_initiator_required(self):
        self.initiator.role = Role.SALES_MANAGER
        with self.assertRaises(ValidationError):
            self.assess()

    def test_release_approval_required(self):
        with self.assertRaises(ValidationError):
            self.assess(status="DRAFT")
