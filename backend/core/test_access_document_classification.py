"""Tests for nonbinding VERIDIAN document-access classifications."""

from django.test import SimpleTestCase

from .models import Document
from .access_permission_catalog import PERMISSION_BY_CODE
from .access_document_classification import (
    DOCUMENT_CLASSIFICATIONS,
    DOCUMENT_CLASSIFICATION_BY_KIND,
    describe_document_kind,
    document_access_granted,
)


class DocumentAccessClassificationTests(SimpleTestCase):

    def test_generated_document_kinds_are_covered_exactly(self):
        expected = {value for value, label in Document.Kind.choices}
        actual = {
            item.kind for item in DOCUMENT_CLASSIFICATIONS
            if item.generated_document_supported
        }
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 4)

    def test_document_kinds_and_permissions_are_unique(self):
        kinds = [item.kind for item in DOCUMENT_CLASSIFICATIONS]
        permissions = [
            item.view_permission for item in DOCUMENT_CLASSIFICATIONS
        ]
        self.assertEqual(len(kinds), len(set(kinds)))
        self.assertEqual(len(permissions), len(set(permissions)))
        self.assertEqual(len(DOCUMENT_CLASSIFICATION_BY_KIND), 5)

    def test_every_document_has_an_independent_view_permission(self):
        for item in DOCUMENT_CLASSIFICATIONS:
            with self.subTest(kind=item.kind):
                definition = PERMISSION_BY_CODE[item.view_permission]
                self.assertEqual(definition.action, "view")
                self.assertEqual(definition.category, "documents")
                self.assertTrue(definition.project_scoped)
                self.assertEqual(
                    describe_document_kind(item.kind),
                    item,
                )

    def test_generated_documents_are_not_assumed_signed(self):
        for item in DOCUMENT_CLASSIFICATIONS:
            with self.subTest(kind=item.kind):
                self.assertFalse(item.signed_document_verified)

    def test_satisfaction_survey_remains_unimplemented(self):
        survey = describe_document_kind("SATISFACTION_SURVEY")
        self.assertIsNotNone(survey)
        self.assertFalse(survey.generated_document_supported)
        self.assertFalse(survey.signed_document_verified)
        self.assertNotIn(
            "SATISFACTION_SURVEY",
            {value for value, label in Document.Kind.choices},
        )

    def test_classification_never_grants_document_access(self):
        for item in DOCUMENT_CLASSIFICATIONS:
            with self.subTest(kind=item.kind):
                self.assertFalse(
                    document_access_granted(None, item.kind)
                )
                self.assertFalse(
                    document_access_granted(
                        object(),
                        item.kind,
                        project=object(),
                    )
                )

    def test_unknown_document_types_fail_closed(self):
        self.assertIsNone(describe_document_kind("UNKNOWN"))
        self.assertFalse(
            document_access_granted(None, "UNKNOWN")
        )
