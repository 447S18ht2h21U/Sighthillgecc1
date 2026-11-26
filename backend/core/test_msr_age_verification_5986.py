"""Focused MSR age verification security tests."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from .models import Role

from .msr_age_verification_5985 import (
    CATEGORY,
    VERIFIER,
    VERIFIED_AT,
    REQUEST,
    prepare_age_edit,
    require_age_verification,
    clear_age_verification,
    validate_age_fields,
)

from .maryland_cancellation_calendar_5983 import (
    ADULT_UNDER_65,
    AGE_65_OR_OLDER,
)


class MSRAgeVerificationTests5986(SimpleTestCase):

    def setUp(self):
        self.actor = SimpleNamespace(
            pk=uuid4(),
            role=Role.SALES_ASSOCIATE,
            is_active=True,
        )

        self.project = SimpleNamespace(
            sales_associate_id=self.actor.pk,
        )

        self.identity = {
            "customer": "Fictional Customer",
            "contact": "Fictional Customer",
            "customer_email": "fictional@example.invalid",
        }

    def edit(self, previous=None, incoming=None, actor=None):
        return prepare_age_edit(
            actor=actor or self.actor,
            project=self.project,
            previous=(
                self.identity if previous is None else previous
            ),
            incoming=(
                self.identity if incoming is None else incoming
            ),
        )

    def verified(self, category=ADULT_UNDER_65):
        return self.edit(incoming={
            **self.identity,
            CATEGORY: category,
            REQUEST: True,
        })

    def test_under_65_verification(self):
        result = self.verified()

        self.assertEqual(result[CATEGORY], ADULT_UNDER_65)
        self.assertEqual(result[VERIFIER], str(self.actor.pk))
        self.assertIsNotNone(
            datetime.fromisoformat(
                result[VERIFIED_AT]
            ).utcoffset()
        )
        self.assertNotIn(REQUEST, result)

        require_age_verification(result)

    def test_65_or_older_verification(self):
        result = self.verified(AGE_65_OR_OLDER)

        self.assertEqual(result[CATEGORY], AGE_65_OR_OLDER)

        require_age_verification(result)

    def test_unverified_draft_can_be_saved(self):
        result = self.edit()

        self.assertNotIn(CATEGORY, result)

        validate_age_fields(result)

    def test_unverified_submission_rejected(self):
        with self.assertRaises(ValidationError):
            require_age_verification(self.identity)

    def test_invalid_categories_rejected(self):
        for category in (
            "", None, "UNKNOWN", "UNDER_18", 65, True
        ):
            with self.subTest(category=category):
                with self.assertRaises(ValidationError):
                    self.verified(category)

    def test_browser_identity_and_timestamp_not_trusted(self):
        false_actor = str(uuid4())

        result = self.edit(incoming={
            **self.identity,
            CATEGORY: AGE_65_OR_OLDER,
            REQUEST: True,
            VERIFIER: false_actor,
            VERIFIED_AT: "2000-01-01T00:00:00+00:00",
        })

        self.assertEqual(
            result[VERIFIER], str(self.actor.pk)
        )
        self.assertNotEqual(result[VERIFIER], false_actor)
        self.assertNotEqual(
            result[VERIFIED_AT],
            "2000-01-01T00:00:00+00:00",
        )

    def test_fabricated_verification_without_confirmation_rejected(self):
        with self.assertRaises(ValidationError):
            self.edit(incoming={
                **self.identity,
                CATEGORY: ADULT_UNDER_65,
                VERIFIER: str(self.actor.pk),
                VERIFIED_AT: "2026-11-25T12:00:00+00:00",
            })

    def test_other_sales_associate_rejected(self):
        other = SimpleNamespace(
            pk=uuid4(),
            role=Role.SALES_ASSOCIATE,
            is_active=True,
        )

        with self.assertRaises(ValidationError):
            self.edit(
                actor=other,
                incoming={
                    **self.identity,
                    CATEGORY: ADULT_UNDER_65,
                    REQUEST: True,
                },
            )

    def test_manager_cannot_attest_as_sales_associate(self):
        manager = SimpleNamespace(
            pk=self.actor.pk,
            role=Role.SALES_MANAGER,
            is_active=True,
        )

        with self.assertRaises(ValidationError):
            self.edit(
                actor=manager,
                incoming={
                    **self.identity,
                    CATEGORY: AGE_65_OR_OLDER,
                    REQUEST: True,
                },
            )

    def test_inactive_employee_rejected(self):
        self.actor.is_active = False

        with self.assertRaises(ValidationError):
            self.verified()

    def test_existing_verification_preserved(self):
        original = self.verified()

        result = self.edit(
            previous=original,
            incoming={
                **original,
                "scope": "Updated fictional work",
            },
        )

        for key in (CATEGORY, VERIFIER, VERIFIED_AT):
            self.assertEqual(result[key], original[key])

    def test_existing_metadata_cannot_be_overwritten(self):
        original = self.verified()

        result = self.edit(
            previous=original,
            incoming={
                **original,
                VERIFIER: str(uuid4()),
                VERIFIED_AT: "2000-01-01T00:00:00+00:00",
            },
        )

        self.assertEqual(
            result[VERIFIER], original[VERIFIER]
        )
        self.assertEqual(
            result[VERIFIED_AT], original[VERIFIED_AT]
        )

    def test_changed_category_requires_confirmation(self):
        original = self.verified()

        with self.assertRaises(ValidationError):
            self.edit(
                previous=original,
                incoming={
                    **original,
                    CATEGORY: AGE_65_OR_OLDER,
                },
            )

    def test_changed_customer_identity_invalidates_attestation(self):
        original = self.verified()

        for key in (
            "customer", "contact", "customer_email"
        ):
            with self.subTest(key=key):
                result = self.edit(
                    previous=original,
                    incoming={
                        **original,
                        key: "Different fictional identity",
                    },
                )

                for field in (
                    CATEGORY, VERIFIER, VERIFIED_AT
                ):
                    self.assertNotIn(field, result)

                with self.assertRaises(ValidationError):
                    require_age_verification(result)

    def test_revision_does_not_inherit_verification(self):
        original = self.verified()

        revised = clear_age_verification(original)

        for key in (CATEGORY, VERIFIER, VERIFIED_AT):
            self.assertNotIn(key, revised)
            self.assertIn(key, original)

        with self.assertRaises(ValidationError):
            require_age_verification(revised)

    def test_confirmation_requires_boolean(self):
        with self.assertRaises(ValidationError):
            self.edit(incoming={
                **self.identity,
                CATEGORY: ADULT_UNDER_65,
                REQUEST: "true",
            })

    def test_incomplete_verification_rejected(self):
        original = self.verified()

        for key in (VERIFIER, VERIFIED_AT):
            with self.subTest(key=key):
                incomplete = dict(original)
                incomplete.pop(key)

                with self.assertRaises(ValidationError):
                    require_age_verification(incomplete)

    def test_naive_timestamp_rejected(self):
        original = self.verified()

        original[VERIFIED_AT] = "2026-11-25T12:00:00"

        with self.assertRaises(ValidationError):
            require_age_verification(original)

    def test_original_snapshot_not_mutated(self):
        original = self.verified()
        saved = dict(original)

        self.edit(
            previous=original,
            incoming={
                **original,
                "customer": "Different fictional customer",
            },
        )

        self.assertEqual(original, saved)
