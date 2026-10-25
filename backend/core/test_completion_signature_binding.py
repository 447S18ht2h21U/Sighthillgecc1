"""Synthetic envelope-binding consistency regression tests."""

import copy
from uuid import uuid4
from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError
from .documents import canonical_hash
from .completion_signature_binding import validate_envelope_binding
from . import test_release as release_tests


@override_settings(DEBUG=True)
class CompletionSignatureBindingTests(TestCase):
    setUp = release_tests.ReleaseTests.setUp
    edit_submit = release_tests.ReleaseTests.edit_submit
    approve = release_tests.ReleaseTests.approve
    setup_review = release_tests.ReleaseTests.setup_review
    setup_release = release_tests.ReleaseTests.setup_release
    authorize_test_customer = release_tests.ReleaseTests.authorize_test_customer
    approval = release_tests.ReleaseTests.approval

    def make_binding(self):
        keys = {
            "release_package_id": str(self.package.pk),
            "release_package_digest": self.package.digest,
            "signing_plan_id": str(self.package.plan_id),
            "signing_plan_digest": self.package.plan.digest,
            "provider_account_id": str(uuid4()),
            "provider_envelope_id": str(uuid4()),
        }
        return {**keys, "binding_digest": canonical_hash(keys)}

    def test_matching_completion_binding_is_not_provider_authentication(self):
        self.setup_release(completion=True)
        self.approval()
        binding = self.make_binding()
        result = validate_envelope_binding(self.package, binding)
        self.assertEqual(result["provider_envelope_id"], binding["provider_envelope_id"])
        self.assertFalse(result["provider_authenticated"])

    def test_substitution_and_digest_changes_rejected(self):
        self.setup_release(completion=True)
        self.approval()
        original = self.make_binding()
        for key, value in (
            ("release_package_id", str(uuid4())),
            ("release_package_digest", "0" * 64),
            ("signing_plan_id", str(uuid4())),
            ("signing_plan_digest", "0" * 64),
            ("provider_account_id", "not-a-uuid"),
            ("provider_envelope_id", str(uuid4())),
            ("binding_digest", "0" * 64),
        ):
            with self.subTest(field=key):
                changed = copy.deepcopy(original)
                changed[key] = value
                with self.assertRaises(ValidationError):
                    validate_envelope_binding(self.package, changed)

    def test_missing_and_commercial_binding_rejected(self):
        self.setup_release(completion=True)
        with self.assertRaises(ValidationError):
            validate_envelope_binding(self.package, None)
        self.assertFalse(validate_envelope_binding(self.package, self.make_binding())["provider_authenticated"])

    def test_commercial_envelope_binding_rejected(self):
        self.setup_release(completion=False)
        self.approval()
        self.assertEqual(self.package.plan.group, "COMMERCIAL")
        binding = self.make_binding()
        with self.assertRaises(ValidationError):
            validate_envelope_binding(self.package, binding)
