# VERIDIAN - Approved Individual Tax Entry Verification Policy

Decision checkpoint: 1907P-4438K
Approval: User expressly approved the CEO as the independent verifier
of individual Corporate Tax Register entries.

## Approved roles

- Comptroller: prepares individual tax entries and supporting evidence.
- CEO: independently verifies individual tax entries.
- No user may verify an entry they prepared.
- The verifier must be an active, currently authorized CEO.
- Verification must preserve preparer and verifier identities, the
  specific entry version, evidence references, decision, and timestamps.
- Every verification decision must be durably audited.
- Verified historical evidence must remain immutable.
- Corrections must use linked, separately controlled audited adjustments.

## Separate approvals

The CEO's individual tax-entry verification is a separate action
from the CEO's final approval of a corporate financial statement.

The existing corporate financial statement policy remains:
Comptroller prepares; CEO independently gives final approval;
no self-approval, durable audit history, immutable approved snapshots.

## Explicitly NOT authorized

- Operational verification endpoint registration or live activation
- Operational database models or migrations
- Accounting posting or financial-report inclusion
- Tax filing, remittance, or payment
- Treating verification as proof of tax liability, correct tax rates,
  legal compliance, or reconciliation
- Deployment, Git staging, commit, or push

## Required protected implementation

1. Verify the active CEO role from authoritative database records.
2. Identify the preparer from the immutable tax-entry record, not
   from caller-supplied identity or an editable form.
3. Require a separately persisted, uniquely identified entry version.
4. Reject self-verification, duplicate decisions, missing evidence,
   unauthorized actors, and changed historical evidence.
5. Create the decision and audit evidence atomically.
6. Keep verification entirely separate from tax posting, filing,
   payment, accounting reconciliation, and statement approval.
7. Test in isolated databases and preserve SHA-256 checkpoints.
8. Obtain separate authorization before any live activation.

Current state: POLICY APPROVED, IMPLEMENTATION NOT YET VERIFIED.
