from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.test import TestCase, override_settings
import hashlib

from .models import CompletionSignatureVerification, CompletionSignatureDocument
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


@override_settings(DEBUG=True)
class CompletionSignatureDocumentTests(TestCase):
    setUp = release_tests.ReleaseTests.setUp
    edit_submit = release_tests.ReleaseTests.edit_submit
    approve = release_tests.ReleaseTests.approve
    setup_review = release_tests.ReleaseTests.setup_review
    setup_release = release_tests.ReleaseTests.setup_release
    make_verification = CompletionSignatureVerificationTests.make_verification

    def make_document(self):
        verification = self.make_verification()
        content = b"%PDF-1.4\nSYNTHETIC TEST DOCUMENT\n%%EOF"
        return CompletionSignatureDocument.objects.create(
            verification=verification,
            document_id="1",
            kind="COMPLETION_NON_FINANCED",
            filename="synthetic-completion.pdf",
            content=content,
            pdf_sha256=hashlib.sha256(content).hexdigest(),
        )

    def test_document_content_and_hash(self):
        document = self.make_document()
        self.assertEqual(
            hashlib.sha256(bytes(document.content)).hexdigest(),
            document.pdf_sha256,
        )

    def test_document_model_rejects_update_and_delete(self):
        document = self.make_document()
        document.filename = "changed.pdf"
        with self.assertRaises(ValidationError):
            document.save()
        with self.assertRaises(ValidationError):
            document.delete()

    def test_document_database_rejects_update(self):
        document = self.make_document()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CompletionSignatureDocument.objects.filter(
                    pk=document.pk
                ).update(filename="changed.pdf")

    def test_document_database_rejects_delete(self):
        document = self.make_document()
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                CompletionSignatureDocument.objects.filter(
                    pk=document.pk
                ).delete()

    def test_document_id_must_be_unique_per_verification(self):
        document = self.make_document()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CompletionSignatureDocument.objects.create(
                    verification=document.verification,
                    document_id="1",
                    kind=document.kind,
                    filename="duplicate.pdf",
                    content=bytes(document.content),
                    pdf_sha256=document.pdf_sha256,
                )
