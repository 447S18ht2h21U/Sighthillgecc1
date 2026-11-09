# VERIDIAN Corporate Tax Register - Protected Readiness Review
Development checkpoint: 1907P-4438J
Last consolidated regression: 1907P-4438I, 66 of 66 Django tests passed.

## Purpose and boundaries
The Corporate Tax Register is a supporting section underneath the four
existing corporate financial statements. It is not a fifth statement.
The approved Tax Register and Prepare Tax Entry screen designs remain unchanged.

This checkpoint documents isolated prototype development, not deployment,
production accounting acceptance, or permission to calculate or remit taxes.

## Verified in isolated development
- Active Comptroller preparation authority; other preparation actors denied.
- Tax year and accounting period captured separately.
- Required reference, amount, classification, and date validation.
- Current approved MSR identity checked through VERIDIAN's shared binding.
- Cancelled projects, wrong MSRs, mismatched versions, and forged addresses denied.
- Historical MSR snapshot fingerprint carried into the draft evidence.
- The delivery address is optional and separate from billing/installation.
- Missing delivery address is NOT_PROVIDED.
- Supplied delivery address is UNVERIFIED_IF_SUPPLIED.
- Audit integration exercised in authorized disposable SQLite tests.
- The isolated audit service denies unauthorized environments and test settings.
- Evidence fingerprints detect changes to the in-memory evidence package.

## Important limitations
- No operational tax database model, migration, or public API was activated.
- Evidence references are not proof that attached documents are authentic.
- Test audit events are not deployed tax-entry records or production audit history.
- The evidence package is not durable tax-entry storage.
- The prototype uses the current approved MSR for new draft preparation.
  Existing captured evidence does not automatically update after an MSR revision.
- A passed test does not establish actual tax liability or filing compliance.
- Tax jurisdiction, legal tax treatment, and rate determination require
  separately established evidence and applicable professional review.
- Accounting reconciliation and financial-report inclusion are not approved.
- No tax-entry verification, posting, filing, or payment is authorized.

## Unresolved governance decisions
1. Designate an authorized independent verifier for individual tax entries.
2. Define verification evidence and the required two-person separation.
3. Approve immutable tax-entry persistence and audited adjustment/version rules.
4. Define jurisdiction-specific filing requirements and due-date evidence.
5. Define independently evidenced accounting posting and reconciliation.
6. Separately authorize operational API registration, database changes,
   testing against approved environments, and any deployment.

Corporate financial reporting remains subject to the approved policy:
Comptroller prepares; CEO independently gives final report approval;
no self-approval, with durable audit and immutable approved snapshots.
That policy does not automatically appoint the CEO as tax-entry verifier.

## Development workflow
Comptroller prepares draft
  -> validate fields and supporting references
  -> bind to current approved MSR where project-related
  -> capture addresses, MSR version, and snapshot fingerprint
  -> create unverified evidence package
  -> exercise isolated audit tests
  -> STOP: no verification, accounting posting, filing, or payment

## Recovery
Validated source files are listed with SHA-256 fingerprints in
recovery/1907P-4438J/tax-source-evidence.json.
The User Guide original and revised versions are preserved there.

## Governance decision approved at 1907P-4438K

The CEO is now the approved independent verifier of individual
Corporate Tax Register entries. The Comptroller remains the preparer.

The previously unresolved verifier-role decision is **resolved as
policy only**. Individual verification is not yet operational.
Implementation must enforce separate identities, immutable entry
versions, authoritative role checks, and durable atomic audit history.

This does not authorize filing, payment, accounting posting, financial
report inclusion, operational database changes, or deployment.

## Versioned correction checkpoint - 1907P-4438X

Focused results:
- 4438S: 12/12 sequential-version tests passed.
- 4438T: 10/10 latest-version CEO decision tests passed.
- 4438U: 14/14 CEO rejection tests passed.
- 4438V: 5/5 initial correction tests passed.
- 4438W: 7/7 correction rollback/reverification tests passed.

Each listed run was a focused test execution; these results do not
claim an additional consolidated regression.

OUTSTANDING SECURITY CONTROL: The general test-only storage service
must not be permitted to create later versions outside the authenticated
CEO rejection and Comptroller correction workflow.

No operational activation is authorized.

## Tax Revision Safeguard Reconciliation - 1907P-4439E

- 4438Y: Revision storage guard introduced; first run encountered
  12 test errors.
- 4438Z: Programming and fixture errors corrected; 33 of 35
  tests passed, with two historical decision-count failures.
- 4439B: Read-only inspection confirmed the actual assertions.
- 4439D: Both failing assertions corrected; 2 of 2 focused
  tests passed.
- 4439E: Source and documentation recovery reconciliation.

The direct unaudited revision path is now guarded in the isolated
test-only storage implementation. This is not evidence of production
concurrency safety or permission to install or activate tax tables.
