
import re

from django.db import connection
from django.test import TestCase

from .models import (
    ExpeditedSigningAttempt,
    ExpeditedEnvelopeBinding,
    ExpeditedSigningObservation,
    ExpeditedSigningDocument,
)


class ExpeditedDatabaseSchema4568Tests(TestCase):
    databases = {"default"}

    @classmethod
    def setUpClass(cls):
        database = connection.settings_dict
        name = str(database.get("NAME", ""))
        django_memory_uri = re.fullmatch(
            r"file:memorydb_[A-Za-z0-9_]+[?]mode=memory&cache=shared",
            name,
        )

        if (
            database.get("ENGINE") != "django.db.backends.sqlite3"
            or not (name == ":memory:" or django_memory_uri)
        ):
            raise RuntimeError(
                "STOP: Actual test connection is not in-memory SQLite."
            )

        super().setUpClass()

    def constraints(self, model):
        with connection.cursor() as cursor:
            return connection.introspection.get_constraints(
                cursor, model._meta.db_table
            )

    def test_four_real_tables_created(self):
        with connection.cursor() as cursor:
            tables = set(connection.introspection.table_names(cursor))

        for model in (
            ExpeditedSigningAttempt,
            ExpeditedEnvelopeBinding,
            ExpeditedSigningObservation,
            ExpeditedSigningDocument,
        ):
            self.assertIn(model._meta.db_table, tables)

    def test_msr_source_digest_unique_in_database(self):
        self.assertTrue(any(
            item.get("unique")
            and set(item.get("columns") or ())
                == {"msr_id", "source_digest"}
            for item in self.constraints(
                ExpeditedSigningAttempt
            ).values()
        ))

    def test_envelope_id_unique_in_database(self):
        self.assertTrue(any(
            item.get("unique")
            and set(item.get("columns") or ())
                == {"provider_envelope_id"}
            for item in self.constraints(
                ExpeditedEnvelopeBinding
            ).values()
        ))

    def test_retained_document_unique_in_database(self):
        self.assertTrue(any(
            item.get("unique")
            and set(item.get("columns") or ())
                == {"observation_id", "document_id"}
            for item in self.constraints(
                ExpeditedSigningDocument
            ).values()
        ))

    def test_foreign_keys_exist_in_database(self):
        relations = (
            (
                ExpeditedSigningAttempt,
                "msr_id",
                ExpeditedSigningAttempt._meta.get_field(
                    "msr"
                ).remote_field.model._meta.db_table,
            ),
            (
                ExpeditedEnvelopeBinding,
                "attempt_id",
                ExpeditedSigningAttempt._meta.db_table,
            ),
            (
                ExpeditedSigningObservation,
                "binding_id",
                ExpeditedEnvelopeBinding._meta.db_table,
            ),
            (
                ExpeditedSigningDocument,
                "observation_id",
                ExpeditedSigningObservation._meta.db_table,
            ),
        )

        for model, column, target_table in relations:
            self.assertTrue(any(
                item.get("foreign_key")
                and column in (item.get("columns") or ())
                and item["foreign_key"][0] == target_table
                for item in self.constraints(model).values()
            ), (model.__name__, column, target_table))

    def test_retention_columns_exist_in_database(self):
        with connection.cursor() as cursor:
            columns = {
                item.name
                for item in connection.introspection.get_table_description(
                    cursor, ExpeditedSigningDocument._meta.db_table
                )
            }

        self.assertTrue({
            "id", "observation_id", "document_id", "filename",
            "content", "pdf_sha256", "retained_at",
        }.issubset(columns))
