"""Security checks for proposed PostgreSQL immutable evidence guards."""

import unittest

from core.msr_delegation_postgresql_guards import (
    EVIDENCE_TABLES,
    FUNCTION_NAME,
    FUNCTION_SQL,
    installation_statements,
    trigger_statements,
    install_postgresql_evidence_guards,
)


class PostgreSQLEvidenceGuardTests(unittest.TestCase):
    def test_five_evidence_tables(self):
        self.assertEqual(len(EVIDENCE_TABLES), 5)
        self.assertEqual(len(set(EVIDENCE_TABLES)), 5)

    def test_exact_allowlist(self):
        self.assertEqual(
            set(EVIDENCE_TABLES),
            {
                "core_msrdelegationrequest",
                "core_msrdelegationrequestproject",
                "core_msrdelegationdecision",
                "core_msrdelegationtermination",
                "core_msrdelegationprojectinvalidation",
            },
        )

    def test_five_triggers(self):
        self.assertEqual(len(trigger_statements()), 5)

    def test_each_table_covered(self):
        for table, sql in zip(EVIDENCE_TABLES, trigger_statements()):
            self.assertIn(f'ON "{table}"', sql)

    def test_update_and_delete_both_denied(self):
        for sql in trigger_statements():
            self.assertIn("BEFORE UPDATE OR DELETE", sql)

    def test_row_level_protection(self):
        for sql in trigger_statements():
            self.assertIn("FOR EACH ROW", sql)

    def test_trigger_uses_guard_function(self):
        for sql in trigger_statements():
            self.assertIn(f"EXECUTE FUNCTION {FUNCTION_NAME}()", sql)

    def test_function_raises_database_exception(self):
        self.assertIn("RAISE EXCEPTION", FUNCTION_SQL)
        self.assertIn("ERRCODE = '23514'", FUNCTION_SQL)

    def test_installation_statements_explicit(self):
        statements = installation_statements()
        self.assertEqual(len(statements), 6)
        self.assertEqual(statements[0], FUNCTION_SQL)

    def test_no_drop_or_disable_commands(self):
        for sql in installation_statements():
            upper = sql.upper()
            self.assertNotIn("DROP TRIGGER", upper)
            self.assertNotIn("DISABLE TRIGGER", upper)
            self.assertNotIn("DROP TABLE", upper)

    def test_no_mutating_dml(self):
        for sql in installation_statements():
            upper = sql.upper()
            self.assertNotIn("DELETE FROM", upper)
            self.assertNotIn("UPDATE CORE_", upper)
            self.assertNotIn("TRUNCATE", upper)

    def test_installation_denied(self):
        with self.assertRaisesRegex(RuntimeError, "SAFETY STOP"):
            install_postgresql_evidence_guards()

    def test_installation_denied_even_with_arguments(self):
        with self.assertRaisesRegex(RuntimeError, "SAFETY STOP"):
            install_postgresql_evidence_guards(
                object(), authorized=True
            )


if __name__ == "__main__":
    unittest.main()