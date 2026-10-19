from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings

from .models import CompletionSignatureVerification
from . import test_release as release_tests


@override_settings(DEBUG=True)
class CompletionSignatureVerificationTests(TestCase):
    setUp = release_tests.ReleaseTests.setUp
    edit_submit = release_tests.ReleaseTests.edit_submit
    approve = release_tests.ReleaseTests.approve
    setup_review = release_tests.ReleaseTests.setup_review
    setup_release = release_tests.ReleaseTests.setup_release
    def make_verification(self):
        self.setup_release(completion=True)
        return CompletionSignatureVerification.objects.create(
            release_package=self.package,
            verified_by=self.comptroller,
            provider_account_id="SYNTHETIC_TEST_ACCOUNT",
            provider_envelope_id="SYNTHETIC_TEST_ENVELOPE",
            evidence={"synthetic": True, "verified": False},
            digest="0" * 64,
        )

    def test_model_rejects_update_and_delete(self):
        record = self.make_verification()
        record.provider_account_id = "CHANGED"
        with self.assertRaises(ValidationError):
            record.save()
        with self.assertRaises(ValidationError):
            record.delete()

    def test_database_rejects_direct_update(self):
        record = self.make_verification()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CompletionSignatureVerification.objects.filter(
                    pk=record.pk
                ).update(provider_account_id="CHANGED")

    def test_database_rejects_direct_delete(self):
        record = self.make_verification()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CompletionSignatureVerification.objects.filter(
                    pk=record.pk
                ).delete()