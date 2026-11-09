# VERIDIAN User Guide

Business Operations & Management System

This is the development User Guide index. Additional approved
chapters, screenshots and instructions will be added as development
continues.

## Process flowcharts

[VERIDIAN Process Flowcharts](VERIDIAN-User-Guide-Process-Flows-1907P-4407.md)

## Corporate financial reporting review - Step 1907P-4409
[Corporate Financial Reporting Review](VERIDIAN-Corporate-Financial-Review-1907P-4409.md)


## Corporate financial readiness - Step 1907P-4412
[Financial Readiness Controls](VERIDIAN-Financial-Readiness-4412.md)


## Approved corporate financial approval policy - 4413
[Approved Corporate Financial Approval Policy](VERIDIAN-Corporate-Financial-Approval-Policy-4413.md)


## Corporate financial approval integration - 4416
[CEO Financial Approval Integration](VERIDIAN-Financial-CEO-Integration-4416.md)


## Cash evidence reconciliation - Step 1907P-4419
[Cash Evidence Reconciliation](VERIDIAN-Financial-Cash-Evidence-4419.md)


## Read-only cash reconciliation - Step 1907P-4422
[Read-Only Cash Evidence Adapter](VERIDIAN-Financial-Cash-Adapter-4422.md)


## Populated cash reconciliation - Step 1907P-4425
[Populated Cash Reconciliation Tests](VERIDIAN-Cash-Populated-Regression-4425.md)


## Cash evidence exceptions - Step 1907P-4428
[Refund and Payroll Cash Evidence Exceptions](VERIDIAN-Cash-Evidence-Exceptions-4428.md)


## Payroll cash evidence gaps - Step 1907P-4430
[Expanded Payroll Cash Evidence](VERIDIAN-Payroll-Cash-Gaps-4430.md)


## Consolidated cash exceptions - Step 1907P-4431
[Consolidated Cash-Evidence Exceptions](VERIDIAN-Cash-Exception-Inventory-4431.md)


## Consolidated cash readiness - Step 1907P-4432
[Cash Readiness and Missing Evidence](VERIDIAN-Cash-Readiness-4432.md)


## Corporate financial report diagrams - Step 1907P-4435D
[Corporate Financial Reporting Diagrams](VERIDIAN-Corporate-Financial-Reporting-Diagrams-4435D.md)


## Corporate Financial Reporting - Step 1907P-4435X

The consolidated corporate financial reporting regression passed
144 of 144 tests in disposable SQLite. A separate consolidated
financial and contractor-security regression passed 41 of 41.

The approved workflow requires Comptroller preparation and
independent CEO final approval. No self-approval is allowed.
Approved snapshots and audit history must be preserved.

The original contractor settlement timezone mismatch was resolved
for isolated regression testing only. The Django-dependent SQLite
trigger adaptation is not an approved permanent database correction.

Matching financial totals alone do not prove full historical
accounting reconciliation. Production acceptance remains pending.

See:
- VERIDIAN-Corporate-Financial-Reporting-Diagrams-4435D.md
- VERIDIAN-Corporate-Financial-Acceptance-4435X.md

Development regression: PASSED.
Production financial acceptance: PENDING.
Operational activation: NOT AUTHORIZED.

## Corporate Tax Register — Consolidated Design (1907P-4436W)

The visually approved Corporate Tax Register supports the
four corporate financial statements; it is not a fifth statement.

GECC is registered in South Dakota, has an office in Nevada,
and sells equipment in Maryland, Delaware and Virginia.

The approved MSR provides customer and project address evidence,
including its historical approved version. Billing and
installation locations must remain distinct.

The Comptroller prepares evidence-backed tax records.
Tax expense, payable, prepayment and actual payment are
separate accounting classifications.

The individual tax-entry verifier has not yet been authorized.
Unverified entries must not enter financial statements.

The CEO independently approves corporate financial reports.
Approved historical snapshots remain immutable.

See VERIDIAN-Corporate-Tax-Register-Design-4436W.md.

Design review: PASSED.
Production tax and financial acceptance: PENDING.

## Corporate Tax Register - Protected Development Checkpoint (1907P-4438J)

The Corporate Tax Register helps the Comptroller organize evidence-backed tax
drafts. It is a supporting register, not another financial statement.

**Protected preparation workflow:**

1. The Comptroller enters a tax draft with its tax year, accounting period,
   category, amount, jurisdiction, evidence references, and filing status.
2. For project-related entries, VERIDIAN checks the project's current approved
   MSR and captures the approved version and snapshot fingerprint.
3. Billing and installation addresses come from the approved MSR.
4. A delivery address is optional. When supplied, it is clearly marked
   **unverified**; when absent, the record says **not provided**.
5. The prototype creates an unverified evidence package. In isolated tests,
   VERIDIAN's existing audit mechanism records a test-only event.
6. The process **stops** before individual tax-entry verification,
   accounting posting, financial-report inclusion, tax filing, or payment.

An approved MSR revision does not rewrite an earlier captured evidence
package. Supporting-document references alone do not prove authenticity.

**Important outstanding decision:** the individual tax-entry verifier has not
been designated. The CEO's independent final approval of corporate financial
statements does not automatically authorize verification of individual tax
entries.

Technical status: Step 1907P-4438I passed 66 of 66 isolated Django tests.
The tax services remain unregistered, with no operational database activation.
See `VERIDIAN-Tax-Register-Readiness-4438J.md` for outstanding requirements
and test limitations.

## Corporate Tax Register - CEO Verification Policy (1907P-4438K)

**Approved responsibility:** The Comptroller prepares the tax entry.
The CEO independently verifies that individual entry.

The person who prepared an entry cannot verify that same entry.
Verification requires the correct entry version, supporting evidence,
an independent CEO decision, and a permanent audit trail.

After verification, the original evidence remains unchanged.
Corrections must be separately recorded and audited.

**Two distinct CEO decisions:** Verifying an individual tax entry
does not replace the CEO's separate final approval of corporate
financial statements.

Verification does not authorize tax filing, tax payments, accounting
posting, or financial-report inclusion. Those remain blocked.

This policy was approved at Step 1907P-4438K. The verification
service is not yet operational; implementation requires isolated
development and testing.

See `VERIDIAN-Tax-Entry-CEO-Verification-Policy-4438K.md`.

## Corporate Tax Register - Versioned Correction Workflow (1907P-4438X)

### Tax Entry versions and independent decisions

1. The Comptroller prepares a tax-entry version and supporting evidence.
2. The historical version is retained unchanged and preparation is audited.
3. The CEO independently reviews the current version.
4. If verified in the isolated prototype, a separate immutable test
   decision and audit record are created.
5. If rejected, the CEO must provide an explanation. Both the decision
   and explanation remain in the historical record.
6. The original Comptroller preparer may submit corrected evidence using
   the protected correction service. The corrected entry becomes the
   next version, with its own audit record.
7. The CEO must independently review the new version. The prior rejection
   and supporting evidence remain available for historical inspection.

### Remaining development control

The general test-only tax storage service currently supports creating
later versions without requiring the dedicated rejection-correction
pathway. This bypass must be closed before the workflow is considered
fully controlled.

The next safeguard must enforce the rejection-to-correction relationship
at the storage boundary, not only within the correction service. It must
reject unaudited or unauthorized revisions and preserve the independent
CEO decision and historical evidence.

The current implementation is an isolated development prototype.
No operational tax-entry verification, posting, filing, payment,
financial-report inclusion, or deployment has been authorized.

## Tax Revision Safeguard Reconciliation - 1907P-4439E

The isolated Corporate Tax Register now requires authenticated CEO
rejection evidence at the version-storage boundary before Version 2
or later can be created. The correction service supplies the specific
rejection decision, and the storage boundary checks the preceding
version, Comptroller preparer, evidence fingerprint, decision, audit
event, and outbox record.

The original rejected version and its CEO decision are retained.
The corrected version must have new evidence and receives its own
independent CEO decision. No rejected version is overwritten.

Development verification: In the 4438Z regression, 33 of 35 tests
passed; the other two had outdated historical-decision count
assertions. Both affected tests passed individually at 4439D.
A new single-run consolidated 35-test PASS has not been recorded.

Outstanding production-readiness concerns include concurrent
revision/decision consistency, operational database schema and
migration design, and controlled activation authorization.
No live tax verification, filing, posting, payment, or financial
report inclusion is enabled.
