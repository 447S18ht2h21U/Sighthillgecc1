"""Test-only service invocation bridge.

This module is a test, not a production dispatcher.
Only approved disposable in-memory SQLite test databases are allowed.
No application URL or operational dispatcher imports this bridge.
"""

import os
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.db import connection
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from .models import AuditEvent
from .msr_delegation_request_service import MSRDelegationRequest
from .msr_delegation_approval_service import MSRDelegationDecision
from .msr_delegation_termination_service import MSRDelegationTermination
from .msr_delegation_reassignment_service import MSRDelegationProjectInvalidation
from .msr_delegation_api_boundary import PreparedDelegationCommand
from .msr_delegation_service_plan import (
    DelegationServicePlan,
    prepare_service_plan,
)
from .msr_delegation_request_service import create_fixed_msr_delegation_request
from .msr_delegation_approval_service import approve_fixed_msr_delegation
from .msr_delegation_termination_service import terminate_fixed_msr_delegation
from .msr_delegation_reassignment_service import reassign_project_with_msr_invalidation


TEST_SERVICES = {
    "create_fixed_msr_delegation_request": create_fixed_msr_delegation_request,
    "approve_fixed_msr_delegation": approve_fixed_msr_delegation,
    "terminate_fixed_msr_delegation": terminate_fixed_msr_delegation,
    "reassign_project_with_msr_invalidation": reassign_project_with_msr_invalidation,
}


def invoke_only_in_disposable_test(plan):
    """Reach real service functions only inside authorized SQLite tests."""
    allowed_names = {
        ":memory:",
        "file:memorydb_default?mode=memory&cache=shared",
    }

    if (
        connection.vendor != "sqlite"
        or str(connection.settings_dict.get("NAME")) not in allowed_names
        or os.environ.get("VERIDIAN_0073_TEST_INSTALL")
        != "ISOLATED_SQLITE_MEMORY"
        or os.environ.get("VERIDIAN_0074_TEST_INSTALL")
        != "ISOLATED_SQLITE_MEMORY"
    ):
        raise PermissionDenied("Disposable test database authorization required.")

    if type(plan) is not DelegationServicePlan:
        raise PermissionDenied("Invalid service plan.")

    service = TEST_SERVICES.get(plan.operation)
    if service is None:
        raise PermissionDenied("Unknown service operation.")

    if type(plan.arguments) is not tuple:
        raise PermissionDenied("Invalid service arguments.")

    try:
        kwargs = dict(plan.arguments)
    except (TypeError, ValueError):
        raise PermissionDenied("Invalid service arguments.") from None

    if len(kwargs) != len(plan.arguments):
        raise PermissionDenied("Duplicate service arguments.")

    # Defense in depth: a forged plan cannot add or replace service arguments.
    from uuid import UUID
    from .msr_delegation_service_plan import CONTRACTS

    expected_contracts = [
        (action, actor_field, target_field, fields)
        for action, (operation, actor_field, target_field, fields)
        in CONTRACTS.items()
        if operation == plan.operation
    ]
    if not expected_contracts:
        raise PermissionDenied("No approved service contract.")

    matching = []
    for action, actor_field, target_field, fields in expected_contracts:
        permitted = set(fields) | {actor_field}
        if target_field is not None:
            permitted.add(target_field)
        if set(kwargs) != permitted:
            continue
        if any(type(key) is not str for key in kwargs):
            continue
        id_fields = {actor_field}
        if target_field is not None:
            id_fields.add(target_field)
        if any(type(kwargs[name]) is not UUID or not kwargs[name].int
               for name in id_fields):
            continue
        if action in ("surrender", "revoke"):
            correct_kind = (
                "VOLUNTARY_SURRENDER" if action == "surrender"
                else "ADMINISTRATIVE_REVOCATION"
            )
            if kwargs["kind"] != correct_kind:
                continue
        matching.append(action)

    if len(matching) != 1:
        raise PermissionDenied("Invalid or ambiguous service arguments.")

    return service(**kwargs)


class DelegationTransactionBridgeTests(TestCase):
    """All identities and project targets are intentionally nonexistent."""

    def setUp(self):
        self.actor = uuid4()
        self.target = uuid4()
        self.now = timezone.now()
        self.models = (
            MSRDelegationRequest,
            MSRDelegationDecision,
            MSRDelegationTermination,
            MSRDelegationProjectInvalidation,
            AuditEvent,
        )

    def counts(self):
        return tuple(model.objects.count() for model in self.models)

    def command(self, action, values):
        return PreparedDelegationCommand(
            action=action,
            actor_id=self.actor,
            arguments=tuple(sorted(values.items())),
        )

    def assert_denied_without_writes(self, action, values, *, route_target=None):
        before = self.counts()
        plan = prepare_service_plan(
            self.command(action, values),
            route_target=route_target,
        )
        self.assertIsInstance(plan, DelegationServicePlan)

        with self.assertRaises((
            PermissionDenied,
            MSRDelegationRequest.DoesNotExist,
            MSRDelegationDecision.DoesNotExist,
        )):
            invoke_only_in_disposable_test(plan)

        self.assertEqual(self.counts(), before)

    def test_request_reaches_real_service_and_denies_missing_records(self):
        self.assert_denied_without_writes(
            "request",
            {
                "recipient_id": uuid4(),
                "source_associate_id": uuid4(),
                "project_ids": (uuid4(),),
                "starts_at": self.now + timedelta(hours=1),
                "ends_at": self.now + timedelta(days=2),
                "reason": "Documented temporary project coverage",
            },
        )

    def test_approval_reaches_real_service_and_denies_missing_request(self):
        self.assert_denied_without_writes(
            "approve",
            {"reason": "Independent approval test evidence"},
            route_target=self.target,
        )

    def test_surrender_reaches_real_service_and_denies_missing_decision(self):
        self.assert_denied_without_writes(
            "surrender",
            {
                "kind": "VOLUNTARY_SURRENDER",
                "reason": "Documented voluntary surrender evidence",
            },
            route_target=self.target,
        )

    def test_revocation_reaches_real_service_and_denies_missing_decision(self):
        self.assert_denied_without_writes(
            "revoke",
            {
                "kind": "ADMINISTRATIVE_REVOCATION",
                "reason": "Documented executive revocation evidence",
            },
            route_target=self.target,
        )

    def test_reassignment_reaches_real_service_and_denies_missing_project(self):
        self.assert_denied_without_writes(
            "reassign",
            {
                "new_owner_id": uuid4(),
                "reason": "Documented project ownership reassignment",
            },
            route_target=self.target,
        )

    def test_missing_test_authorization_denied_before_service_call(self):
        plan = prepare_service_plan(
            self.command(
                "approve", {"reason": "Independent approval evidence"}
            ),
            route_target=self.target,
        )
        with patch.dict(os.environ, {
            "VERIDIAN_0073_TEST_INSTALL": "DENIED",
        }):
            with self.assertRaises(PermissionDenied):
                invoke_only_in_disposable_test(plan)

    def test_persistent_database_identity_denied_before_service_call(self):
        plan = prepare_service_plan(
            self.command(
                "approve", {"reason": "Independent approval evidence"}
            ),
            route_target=self.target,
        )
        with patch.dict(connection.settings_dict, {
            "NAME": "dev.sqlite3",
        }):
            with self.assertRaises(PermissionDenied):
                invoke_only_in_disposable_test(plan)