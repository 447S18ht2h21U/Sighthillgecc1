# VERIDIAN Corporate Tax Register — Consolidated Design

Step 1907P-4436W

## Design approval

The Corporate Tax Register is an approved supporting section of
Corporate Financial Reporting. It is not a fifth financial statement.

The existing four reports remain:
1. Income Statement
2. Balance Sheet
3. Cash Flow Statement
4. Project Profitability

The seven-column Tax Register design is visually approved.

## GECC multi-state operations

Green Energy Contracting Corporation:
- Registered in South Dakota.
- Maintains an office in Nevada.
- Sells equipment in Maryland, Delaware and Virginia.

These facts identify jurisdictions for review, not confirmed
company-specific tax liabilities.

## MSR integration

Use the approved Master Sales Record as the source of truth.
Preserve the project ID, approved MSR identity and version,
customer billing address, installation location and work type.

Delivery location must be separately identified when applicable.
Customer billing address alone cannot establish tax jurisdiction.

Historical approved MSR snapshots must remain immutable.

## Tax classification

Keep separate:
- Current and deferred income tax expense.
- Other business tax expense.
- Tax payable.
- Tax prepayments or receivables.
- Actual tax payments.

A tax payment must not create duplicate tax expense.
A tax liability is not automatically an operating expense.

No tax liability may be calculated solely from a state code
or by applying an assumed rate to accounting profit.

## Preparation and evidence

Comptroller prepares tax records.
Draft entries need an accounting period, tax type, jurisdiction,
amount, classification, supporting source, evidence, preparer,
reason and audit history.

Missing evidence must never automatically become zero.
Unverified records cannot feed corporate financial reporting.

Verified history must be immutable. Corrections require separately
authorized, versioned adjustment evidence.

## Independent approval

Comptroller prepares corporate financial statements.
CEO independently provides final approval.
No self-approval; durable audit; immutable approved snapshots.

Who independently verifies individual tax entries remains a
PENDING POLICY DECISION. Corporate report approval does not
automatically authorize individual tax-entry verification.

## Remaining acceptance requirements

- Establish tax-entry verifier authority.
- Define tax-account and general-ledger mappings.
- Define source authenticity and document retention.
- Establish reconciliation and period-close controls.
- Define corrections, adjustments and amended returns.
- Review jurisdiction-specific nexus and classification.
- Resolve permanent SQLite settlement-date compatibility.
- Obtain separate operational database and activation approval.

## Verification evidence

Step 4436U: 27 focused design checks passed.
Step 4436V: 30 focused design checks passed.
Corporate financial reporting: 144 consolidated tests passed.

These checks do not certify GAAP compliance, tax liability,
filing readiness or production accounting acceptance.

Operational posting, tax filing and payments remain disabled.
Git staging, commit and push remain separately approval-gated.
