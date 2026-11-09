# VERIDIAN MSR Project Ownership Invalidation - Design Addendum

Checkpoint: 1907P-3837
Status: DESIGN ONLY - NO OPERATIONAL AUTHORIZATION

## Purpose

Preserve the original temporary MSR delegation approval while permanently
invalidating its access to any project reassigned to another Sales Associate.
Unrelated projects in the same approved request remain unaffected.

## Proposed fifth immutable record

Name: MSRDelegationProjectInvalidation

Fields:
- UUID primary key and creation timestamp
- Protected reference to original approved decision
- Protected reference to the exact request/project scope record
- Project identity and prior source Sales Associate identity
- Ownership revision before and after reassignment
- Invalidation timestamp and reason PROJECT_REASSIGNED
- Evidence reference to the initiating reassignment and audit event

Constraints:
- Exact decision, request and project must agree
- One reassignment invalidation per original request/project scope
- Original decision must be APPROVED
- Historical record cannot be updated or deleted
- Duplicate invalidation must never restore access
- No automatic restoration when ownership returns

## Ownership revision safeguard

The project needs durable, monotonically increasing ownership history.
Changing the Sales Associate advances the ownership revision.
Returning to a previous Sales Associate also advances the revision.
Revisions must not be reset or decreased.

Each request/project scope must retain the ownership revision verified
at request construction and rechecked at independent approval.

A mismatched ownership revision blocks approval, even when the current
Sales Associate matches the original source again.

The access evaluator must fail closed if ownership or revision differs,
the recipient is inactive, approval is missing, time has expired,
revocation exists, or an invalidation record exists.

## Reassignment authorization and audit

No operational project reassignment endpoint was identified at Step 3835.
Future reassignment must be restricted to explicitly authorized actors.

Reassignment, revision update, project-level invalidation, and hash-chain
audit evidence must be committed atomically or all rolled back.
A database-level safeguard must handle writes outside the normal API,
including bulk ORM updates. If audit evidence cannot be guaranteed,
an untrusted reassignment must be blocked rather than silently logged.

Use consistent project/request locking order for PostgreSQL.
Do not assume SQLite select_for_update provides PostgreSQL locking.

## Required separate tests

1. Reassignment followed by return before approval: old scope rejected.
2. Reassignment after approval: only affected project access denied.
3. Return to original owner: old scope remains permanently invalid.
4. Scope, decision and invalidation UPDATE/DELETE denied at DB layer.
5. Duplicate decision and invalidation denied.
6. Direct SQL and bulk ORM reassignment cannot bypass safeguards.
7. Atomic rollback on audit failure and concurrent reassignment.
8. Approved time window, roles, identity and fixed scope enforced.
9. SQLite and PostgreSQL isolated database tests independently pass.
10. Existing MSR API regressions remain passing with delegation disabled.

## Deployment boundaries

No change to core/models.py, project API, migration files or permissions.
No migration installation on development, acceptance or production data.
No Git staging, commit, push, or release authorized.
This addendum supplements the Step 3825 blueprint and Step 3829 draft.
The fifth record and ownership revision are proposals until fully reviewed.