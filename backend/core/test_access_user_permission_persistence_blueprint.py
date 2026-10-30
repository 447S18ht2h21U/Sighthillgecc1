"""Tests for the non-executable permission persistence blueprint."""

from dataclasses import FrozenInstanceError

from django.test import SimpleTestCase

from .access_user_permission_persistence_blueprint import (
    DATABASE_SAFEGUARDS,
    PERMISSION_DECISION,
    PERMISSION_REQUEST,
    PERMISSION_TERMINATION,
    RECORDS,
    blueprint_enables_permissions,
    blueprint_installs_migrations,
    blueprint_is_structurally_complete,
)


class UserPermissionPersistenceBlueprintTests(SimpleTestCase):

    def test_three_distinct_record_types(self):
        self.assertEqual(
            {record.name for record in RECORDS},
            {
                "UserPermissionRequest",
                "UserPermissionDecision",
                "UserPermissionTermination",
            },
        )

    def test_blueprint_structurally_complete(self):
        self.assertTrue(blueprint_is_structurally_complete())

    def test_all_records_require_immutability(self):
        self.assertTrue(all(record.immutable for record in RECORDS))

    def test_decisions_and_terminations_are_unique(self):
        self.assertFalse(PERMISSION_REQUEST.unique_parent)
        self.assertTrue(PERMISSION_DECISION.unique_parent)
        self.assertTrue(PERMISSION_TERMINATION.unique_parent)

    def test_request_preserves_identity_and_effective_period(self):
        fields = " ".join(PERMISSION_REQUEST.fields)
        for required in (
            "recipient:",
            "requested_by:",
            "permission_code:",
            "starts_at:",
            "ends_at:",
            "digest:",
        ):
            with self.subTest(field=required):
                self.assertIn(required, fields)

    def test_decision_preserves_independent_authority_evidence(self):
        fields = " ".join(PERMISSION_DECISION.fields)
        for required in (
            "request:",
            "decided_by:",
            "decision:",
            "decided_at:",
            "authority_evidence:",
            "digest:",
        ):
            with self.subTest(field=required):
                self.assertIn(required, fields)

    def test_termination_preserves_separate_evidence(self):
        fields = " ".join(PERMISSION_TERMINATION.fields)
        for required in (
            "decision:",
            "terminated_by:",
            "termination_kind:",
            "terminated_at:",
            "authority_evidence:",
            "digest:",
        ):
            with self.subTest(field=required):
                self.assertIn(required, fields)

    def test_all_evidence_uses_protected_relationships(self):
        for record in RECORDS:
            relationship_fields = (
                field for field in record.fields
                if "foreign key" in field
            )
            for field in relationship_fields:
                with self.subTest(record=record.name, field=field):
                    self.assertIn("protected", field)

    def test_database_guards_cover_critical_integrity(self):
        safeguards = " ".join(DATABASE_SAFEGUARDS).lower()
        for required in (
            "reject updates",
            "reject deletion",
            "independent approval",
            "duplicate decisions",
            "duplicate terminations",
            "atomic evidence",
        ):
            with self.subTest(required=required):
                self.assertIn(required, safeguards)

    def test_expiration_does_not_depend_on_record_update(self):
        safeguards = " ".join(DATABASE_SAFEGUARDS).lower()
        self.assertIn(
            "deny access after expiry even without an expiration record",
            safeguards,
        )

    def test_revocation_and_surrender_end_access(self):
        safeguards = " ".join(DATABASE_SAFEGUARDS).lower()
        self.assertIn(
            "deny access immediately after surrender or revocation",
            safeguards,
        )
        self.assertIn(
            "never reactivate terminated evidence",
            safeguards,
        )

    def test_historical_approvals_remain_preserved(self):
        safeguards = " ".join(DATABASE_SAFEGUARDS).lower()
        self.assertIn(
            "preserve historical approvals when the approver later becomes inactive",
            safeguards,
        )

    def test_sqlite_and_postgresql_both_required(self):
        safeguards = " ".join(DATABASE_SAFEGUARDS).lower()
        self.assertIn(
            "equivalent sqlite and postgresql safeguards",
            safeguards,
        )

    def test_blueprint_metadata_is_frozen(self):
        with self.assertRaises(FrozenInstanceError):
            PERMISSION_REQUEST.immutable = False

    def test_blueprint_cannot_activate_access_or_install_migrations(self):
        self.assertFalse(blueprint_enables_permissions())
        self.assertFalse(blueprint_installs_migrations())