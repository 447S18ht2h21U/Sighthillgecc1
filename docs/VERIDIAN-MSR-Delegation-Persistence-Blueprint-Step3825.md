# VERIDIAN MSR Delegation Persistence Blueprint

Status: DESIGN ONLY - NOT OPERATIONAL
Checkpoint: 1907P-3825
Scope: Temporary, read-only Master Sales Report coverage for Sales Associates.

## 1. Authority

An active Sales Manager initiates a coverage request.
An independently authorized active CEO or Comptroller approves or rejects it.
The manager, recipient, source Sales Associate, and decision-maker
must be four distinct users.

A recipient must be an active Sales Associate.
The source must hold the Sales Associate role at approval time,
but may be inactive to permit departure coverage.

All identities and roles must be verified from trusted database records.
No request-supplied role or approval claim is authoritative.

## 2. Proposed records

A. Delegation Request
- Immutable UUID request identifier.
- Sales Manager, recipient, and source Sales Associate user references.
- Request time, start time, end time, reason.
- Explicit fixed list of selected project identifiers.
- Read-only purpose; no financial, write, signing, or administrative grant.
- Never expand the project list automatically.

B. Request Project Scope
- Immutable request-to-project relationship.
- One record per explicitly approved project.
- Unique request/project pair.
- Project ownership verified against source Sales Associate.
- No implied access to later-created projects.
- Ownership and scope must be revalidated at the approval transaction.

C. Independent Decision
- Separate immutable UUID decision record.
- Protected foreign key to original request.
- APPROVED or REJECTED decision and timestamp.
- Decision-maker identity, reason, and authority evidence.
- At most one final decision for each request.
- Verify the decision-maker against trusted active User records.
- Never replace or delete the original request.

D. Termination Evidence
- Separate immutable record linked to an approved decision.
- Administrative revocation, voluntary surrender, or expiration evidence.
- Date, actor when applicable, reason, and authority evidence.
- Do not overwrite the original decision.
- At most one effective early termination for each approval.
- Natural expiration is enforced by end time even without an event.

## 3. Transaction and database integrity

All recording operations must use atomic transactions.
Approval must lock the pending request and relevant records and
revalidate the participants, ownership, project scope, and time window.

Request, project scope, decision, and termination evidence must receive
database-level immutability protections against UPDATE and DELETE.

Use foreign-key protection and uniqueness constraints.
Require matching request/decision/project relationships.
Reject missing evidence, duplicate decisions, overlapping termination
records, unauthorized actors, and invalid time relationships.

Audit events must use VERIDIAN's existing hash-chain audit service.
A recording operation must roll back if auditing fails.
Historical approval authority is established at decision time;
later changes to an approver account must not erase that evidence.

The recipient's current active status and the grant's expiration or
revocation must still be checked when access is eventually evaluated.

## 4. Database isolation

No database schema change is authorized by this blueprint.
Do not apply migrations to development, acceptance, production,
restore, financial-safeguard, or contractor-safeguard databases.

The existing 0071 and 0072 migration installation protections must
remain intact. Any future migration requires separate review,
isolated testing, and explicit installation authorization.

Test both SQLite and PostgreSQL safeguards independently.
Do not use production or acceptance databases for initial testing.

## 5. Operational integration - explicitly deferred

No existing MSR API, visibility policy, serializer, or route changes.
No live delegation grants.
No general permission authority matrix activation.
No additional access to payroll, financial reports, signing,
technician assignments, or other project administration.

A future read path must verify authenticated active identity,
approved immutable evidence, current time, absence of termination,
and exact eligible project scope before allowing access.
Any failed verification must deny access.

## 6. Required verification before activation

- Request and decision separation tests.
- Immutable record and DB-trigger tests on SQLite and PostgreSQL.
- Concurrent approval and revocation race-condition tests.
- Missing/forged/inactive identity tests.
- Project ownership change and fixed-scope tests.
- Expiration, surrender, and revocation tests.
- Audit-failure rollback and historical-evidence preservation.
- Existing MSR API security regression.
- Recovery, migration-identity, and full UI acceptance verification.

This document describes proposed safeguards only.
It does not establish operational authorization.