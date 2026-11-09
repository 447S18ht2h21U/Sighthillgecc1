"""Verify immutable evidence is protected by automatic test migrations."""

import unittest
from unittest.mock import patch

from django.db import connection
from django.test import TestCase

from core.msr_delegation_sqlite_guards import EVIDENCE_TABLES


class AutomaticEvidenceGuardTests(TestCase):
    def test_all_ten_triggers_exist_before_test_code_installs_anything(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            )
            installed = {row[0] for row in cursor.fetchall()}
        expected = {
            f"msr_immutable_{table}_{action}"
            for table in EVIDENCE_TABLES
            for action in ("update", "delete")
        }
        self.assertEqual(len(expected), 10)
        self.assertTrue(expected.issubset(installed))

    def test_five_evidence_tables_exist(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in cursor.fetchall()}
        self.assertTrue(set(EVIDENCE_TABLES).issubset(tables))


class MigrationGuardSourceTests(unittest.TestCase):
    def test_migration_guard_rejects_unapproved_execution(self):
        import importlib
        module = importlib.import_module(
            "core.migrations.0074_msr_delegation_test_evidence_guards"
        )
        class Connection:
            vendor = "sqlite"
            settings_dict = {"NAME": ":memory:"}
        class Editor:
            connection = Connection()
        with patch.dict("os.environ", {
            "VERIDIAN_0074_TEST_INSTALL": ""
        }):
            with self.assertRaisesRegex(RuntimeError, "SAFETY STOP"):
                module.install_test_guards(None, Editor())

    def test_migration_guard_rejects_persistent_database(self):
        import importlib
        module = importlib.import_module(
            "core.migrations.0074_msr_delegation_test_evidence_guards"
        )
        class Connection:
            vendor = "sqlite"
            settings_dict = {"NAME": "C:/persistent/dev.sqlite3"}
        class Editor:
            connection = Connection()
        with patch.dict("os.environ", {
            "VERIDIAN_0074_TEST_INSTALL": "ISOLATED_SQLITE_MEMORY"
        }):
            with self.assertRaisesRegex(RuntimeError, "SAFETY STOP"):
                module.install_test_guards(None, Editor())

    def test_migration_is_not_reversible(self):
        import importlib
        module = importlib.import_module(
            "core.migrations.0074_msr_delegation_test_evidence_guards"
        )
        with self.assertRaisesRegex(RuntimeError, "SAFETY STOP"):
            module.refuse_reverse(None, None)