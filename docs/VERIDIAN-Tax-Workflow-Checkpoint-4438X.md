# VERIDIAN Corporate Tax Register - Workflow Checkpoint 4438X

## Verified prototype capabilities

- Comptroller prepares a test-only tax-entry version.
- Stored versions and CEO decisions are immutable in disposable SQLite.
- Sequential version numbering is tested.
- The CEO must independently review the current version.
- The CEO can verify or reject in test-only decision records.
- Rejection requires an explanation and an audit record.
- The protected correction service creates new evidence and a new version.
- The prior rejected version and CEO decision remain unchanged.
- Correction audit failure rolls back the new version.
- A corrected version can receive a separate CEO test decision.

## Outstanding security requirement

Prevent direct creation of Version 2 or later through the general
storage service without a verified, audited rejection transition.
This enforcement must be at the storage boundary and must preserve
rejection history, actor permissions, and complete audit rollback.

## Scope

These safeguards have been tested only using disposable databases.
There are no registered operational tax routes, installed tax tables,
live CEO verification permissions, filing, posting, or payment actions.

The four existing financial statements remain separate and unchanged.
The Comptroller prepares corporate financial reports and the CEO
independently approves the final reports under the separately approved
report-approval policy.

## Documentation sources

- User Guide: VERIDIAN-User-Guide.md
- Readiness review: VERIDIAN-Tax-Register-Readiness-4438J.md
- CEO policy: VERIDIAN-Tax-Entry-CEO-Verification-Policy-4438K.md
- Protected source checkpoints: 4438S, 4438U, 4438V and 4438W

## Tax Revision Safeguard Reconciliation - 1907P-4439E

The storage-level revision boundary now checks the preceding
version's authentic, audited CEO rejection. Direct unaudited
Version 2 creation is denied by the isolated prototype.

The test history must be reported precisely: 33/35 in the last
three-module run, followed by 2/2 previously failing focused
assertion tests passing after correction. The entire suite has
not been rerun as one successful 35-test batch.

Remaining controls before production consideration: concurrency
and transaction serialization review, database migration review,
authorization review, and a separately approved release process.
All operational tax actions remain disabled.
