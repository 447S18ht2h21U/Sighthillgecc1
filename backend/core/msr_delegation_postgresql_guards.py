"""PostgreSQL MSR delegation evidence guard definitions.

These SQL statements are NOT installed by this module.
Installation requires a separately authorized database migration,
verified PostgreSQL identity, atomic execution, and behavioral tests.
"""

EVIDENCE_TABLES = (
    "core_msrdelegationrequest",
    "core_msrdelegationrequestproject",
    "core_msrdelegationdecision",
    "core_msrdelegationtermination",
    "core_msrdelegationprojectinvalidation",
)

FUNCTION_NAME = "gecc_msr_delegation_evidence_immutable"

FUNCTION_SQL = """
CREATE FUNCTION gecc_msr_delegation_evidence_immutable()
RETURNS trigger
LANGUAGE plpgsql
AS $msr_evidence$
BEGIN
    RAISE EXCEPTION 'MSR delegation evidence is immutable'
        USING ERRCODE = '23514';
END;
$msr_evidence$;
"""


def trigger_statements():
    """Return exactly five explicit UPDATE/DELETE-blocking triggers."""
    statements = []
    for table in EVIDENCE_TABLES:
        trigger = "msr_immutable_" + table
        statements.append(
            f'CREATE TRIGGER "{trigger}" '
            f'BEFORE UPDATE OR DELETE ON "{table}" '
            "FOR EACH ROW EXECUTE FUNCTION "
            f"{FUNCTION_NAME}();"
        )
    return tuple(statements)


def installation_statements():
    """SQL definition only; does not execute or connect."""
    return (FUNCTION_SQL,) + trigger_statements()


def install_postgresql_evidence_guards(*args, **kwargs):
    """Fail closed until a reviewed, identity-guarded migration exists."""
    raise RuntimeError(
        "SAFETY STOP: PostgreSQL MSR evidence guard installation "
        "has not been authorized or implemented."
    )