# GECC MVP requirements and readiness review

Review date: October 7, 2026, Eastern time.

**Conclusion: the demonstrated local commercial workflow is working, but a requirements-complete MVP and an operational production release are not yet ready.** Passing the current tests and reviewing the screens does not establish coverage of every approved requirement. The findings below identify concrete remaining work without reopening decisions already approved by the owner.

## Basis and scope

Implementation reviewed: `6cc4c00c73d85c1aa2d0be82f19e43b6dcd1219c`, branch `gecc/audit-history-2026-10-07`. Owner testing uses the Windows local development installation. This review used source/code inspection, recorded automated results and the owner's reported screen/document checks; it did not access the owner's local database independently.

The six original specification files were retrieved from `main`, whose observed head was `039e6fd8982a4cdc45af1aaf3305b3b4b9bda8f3`. Links below pin that source revision. The approved [implementation architecture v1.2](GECC-Implementation-Architecture-v1.2.html) reconciles conflicting source rules. Explicit later owner decisions govern the affected topics; the Requirements Baseline governs older contradictions; the MVP defines the first-slice boundary; consistent Sprint detail supplies implementation criteria.

Decisions retained:

- Five **calendar** days after the later customer contract/invoice signature, with the separate later applicable cancellation deadline. Do not return to the older three-day rule.
- Keep the 50% deposit option and 100%-at-completion option. This product choice does not constitute approval of its applicability to every live transaction.
- Every approved MSR field remains immutable; corrections require a new approved version.
- Only the Comptroller manages business accounts and business configuration; no additional System Administrator business role is introduced.
- Customer-first contract/invoice signing; GECC-first completion-certificate signing, with recorded Comptroller substitution when applicable.
- No legacy-data migration is required under the owner's later decision.
- Simplifying review of multiple PDFs remains deferred until after MVP.

The original MVP file labels itself a proposed implementation baseline; the approved architecture adopts its foundation scope. Conflicting role details remain subject to the documented reconciliation rather than being silently promoted into a new policy.

Electronic signatures, scheduling, operational completion, payment verification, commissions, accounting, inventory and advanced dashboards remain outside the original foundation MVP. Sandbox work on some of those features does not make the full later workflows operational.

## Implemented and demonstrated

| MVP area | Evidence and present limits |
|---|---|
| Local active-user login and commercial access | Local password login, CSRF and 30-minute server idle timeout; account creation/edit/reset/deactivation controls. Owner checked account behavior and assigned-record isolation. Production identity is separate and absent. |
| Customers and contacts | Scoped edits, required change notes, stale-revision checks, single primary contact, confirmed replacement, archive/restore and no delete API. Owner tested these and confirmed Approved Version 4.0 stayed unchanged. Contact duplicate warnings remain missing. |
| Projects and MSRs | Unique codes, linked customer/location and assigned Sales Associate/Manager; draft validation, submission, separate approval/rejection, immutable approvals, sequential revisions, cancellation/reopening and retained version history. Location display consistency and approval-history presentation remain incomplete. |
| Contract/invoice preparation | Approved-template hashes, exact approved snapshots, version/document IDs, immutable retained PDFs and checksum-checked downloads. Owner confirmed populated test details, layout and older-version preservation. Invoice line quantity/unit-price presentation remains incomplete. These are unsigned preparation copies, not production signing release. |
| Search/filtering | Customer/contact text matches, project code/location/customer matches, status filters, ordering and pagination. Owner checked Approved/Cancelled filtering, search by Test Contact Two, archived filtering and reset. Revised MSR installation addresses are not searched independently of the original project location. |
| Audit storage and screen | Atomic business audit/outbox commits, database append-only guards, hash-chain verification command; Comptroller read-only history, reasons, before/after values, Eastern dates and pagination. Coverage and role-specific visibility gaps remain below. |

### Automated evidence

[GitHub Actions push run 37665137960](https://github.com/447S18ht2h21U/Sighthillgecc1/actions/runs/37665137960) completed successfully at the reviewed implementation commit: **183 PostgreSQL backend tests**, TypeScript/Vite build and desktop/mobile browser review. The local suite also passed, with four PostgreSQL-specific tests skipped. Django system and migration checks passed.

A duplicate pull-request workflow, [37665193250](https://github.com/447S18ht2h21U/Sighthillgecc1/actions/runs/37665193250), was still waiting in browser dependency installation at the review checkpoint; its backend job had passed. Confirm required release/merge checks are complete before integration. That pending duplicate run is not described as a completed pass here.

These tests validate implemented behavior. They do **not** cover the missing requirements identified below. This documentation review adds no application behavior and does not require another full regression run.

### Owner acceptance evidence

On October 7 the owner confirmed:

- User creation, assigned-record isolation, deactivation/login blocking, reactivation, role/password changes and protected self-role/active controls.
- Customer phone correction; creation/editing of two contacts; transfer of primary status while retaining the former contact; archive/restore; unchanged Approved Version 4.0.
- Project and customer searches, status filtering and clearing filters.
- Audit Event 160: the customer phone changed from blank to `301-555-0111`, with the recorded Comptroller identity, time and reason visible.
- Audit dates included the October 7 event and excluded it when both dates were October 6; reset restored the list; pagination moved between pages 1 and 2 of 167 records; the global Audit history button was absent for Manager.

Previously the owner completed three fictional sandbox signing workflows, verified both signatures, invoice payment initials and completion histories, and opened all seven retained files from an isolated restore. Those are sandbox and local recovery results, not actual work/payment verification or production disaster-recovery certification.

## Remaining MVP findings

The `RV-M` IDs identify review findings, not newly approved requirements or silent policy amendments.

| Finding | Requirement and observed gap | Concrete completion criterion |
|---|---|---|
| **RV-M01 — Audit completeness** | MVP §9; BL R-030/031; Sprint 03. Business mutations are logged, but login success/failure/logout/session expiry, denied actions, restricted record/document access and audit-history access/search are not comprehensively recorded. Events lack a universal immutable actor role at action time and command/source marker. Draft-edit events retain the new snapshot, without an explicit before/after field comparison. | Add safely recorded authentication/access/denial events and prospective role/source metadata; keep credentials out of logs. Preserve existing events/digests and mark unavailable historic metadata honestly. Demonstrate successful/failed login, denied access, restricted download and draft-edit coverage without creating recursive audit reads or extending idle sessions. |
| **RV-M02 — Role-view reconciliation** | MVP §§3/8 and Sprint 03 audit-access rules allow assigned/limited audit visibility beyond the Comptroller and approved-project viewing for Installation Manager. Current commercial scopes return no records to Installation Manager, and all audit reads are Comptroller-only. The owner's check confirmed current UI behavior; it is not a formal waiver of the source permissions. | Keep global audit history Comptroller-only. Implement authorized project-scoped history and an approved-information-only Installation Manager view after defining the assignment/field scope, or record a controlled scope amendment. Never grant global data access merely to satisfy a role label. Preserve denial of Installation Manager commercial approval. |
| **RV-M03 — Priced invoice lines** | MVP §11 and EXT invoice mapping specify descriptions, quantities and unit prices. MSR equipment/material lines contain description/quantity only. The invoice currently represents one aggregate approved amount plus detail; it does not explicitly present priced-line quantity/unit price. Owner approval of appearance is not a documented waiver of this field requirement. | Represent approved priced lines explicitly and reconcile discount/tax/total. A clearly approved project-package line with quantity 1 and the approved package price may be appropriate; itemized equipment prices require actual commercial inputs. Do not invent component prices by dividing a total. Preserve old approved MSRs/PDFs. |
| **RV-M04 — Current installation address** | MVP §§4–6; BL R-005/006/013. Editing `snapshot.project_location` does not change `Project.location`. Project headers/cards and location search use the original project field, while PDFs use the approved snapshot address. | Define current versus historical address presentation; show the authoritative approved address and clearly identify pending changes. Search the applicable approved/pending addresses without rewriting older versions. Test approval of an address revision against the project list, search and generated PDFs. |
| **RV-M05 — Contact duplicates** | BL R-013 and Sprint 04 require likely-duplicate customer/contact/location warnings. Customer name/address and same-customer project-location checks exist; contact creation has no comparable duplicate warning/override. | Add scoped candidate matching and an explicit recorded override for likely duplicates. Warn without exposing other users' records, and allow legitimate shared contact details after review. |
| **RV-M06 — Visible approval/rejection trace** | MVP §§6.3/6.4/12 require approval information and retained rejection history. The API stores approver/time, and audit events preserve decisions, but the project UI shows approved version/snapshot without the approver/time and does not expose each prior decision attempt to assigned reviewers. | Show who approved and when on the approved version; show version-bound submission/rejection/approval decisions and reasons in an authorized project view. Resubmission must not hide earlier rejection evidence. |

RV-M04 is based on code inspection, not a newly executed address-revision test in the owner's database. The other gaps are likewise requirement/code findings; no unreported owner test is claimed.

One scope clarification also remains: architecture §10 specifies multi-select work types, while the current MSR uses free-text scope and editable equipment/material lines. Confirm whether catalog/checkbox selections belong in the foundation acceptance baseline or are explicitly deferred. The narrower MVP describes scope as proposed-work text; the review does not invent a catalog or expand finance/installation scope.

## Separate prerequisites for operational deployment

| Prerequisite | Current state / evidence needed |
|---|---|
| **RV-P01 — Production identity** | Cognito password/SMS MFA adapter, provisioning/revocation integration and production authentication tests are absent. Local `dev-login` is deliberately unavailable outside development. |
| **RV-P02 — Hosted operations** | AWS infrastructure, production PostgreSQL deployment, protected document storage, Secrets Manager/IAM configuration, monitoring/alerts and worker delivery are not provisioned. A localhost Django development server is not the selected production service. |
| **RV-P03 — Approved configuration versions** | The approved architecture §7 calls for Comptroller draft/submit/approve/effective-date controls, pinned usage and immutable version history. Current rules/templates are constants/manifests; no corresponding configuration entity or approval UI exists. Apply this first to values/templates active in the MVP; later finance configuration can wait for its slice. |
| **RV-P04 — Template activation** | Source artwork/template availability and test rendering are demonstrated. The external register and architecture still require controlled production-template approval and resolution of business identity/license, payment/cancellation/warranty and applicable legal terms. Keep the selected five-calendar-day and 50% option; do not equate sandbox PDF acceptance with live-contract approval. |
| **RV-P05 — Recovery** | The October 7 local/external backup and restore succeeded. The verified 08:17:35 backup predates today's new account/customer/contact/audit changes. Take a fresh consistent backup before the next database-changing upgrade. Automated protected backups, independent audit anchors, failover and measured end-to-end no-loss/15-minute recovery evidence remain absent. |
| **RV-P06 — Release integration and handover** | Development is on stacked draft branches/PRs, not a signed-off operational release. Establish one reviewed release revision, finish required checks, rehearse upgrades/rollback, complete the remaining acceptance matrix and provide operating/training instructions. The owner must approve operational release after the actual gaps are closed. |

The no-data-loss and 15-minute recovery targets remain requirements. The successful manual restore does not prove those production targets, regional-disaster coverage or external-provider availability.

## What does not block foundation MVP completion

The original MVP excludes live electronic signing, installation scheduling/completion, payment verification, AR/AP processing, commissions, inventory/assets/loans, financial reporting and advanced notifications/dashboards. Their absent production implementation is tracked for later slices, rather than counted as missing foundation features.

The existing sandbox signing/retention evidence is useful progress beyond the original MVP. Production send/lifecycle controls, real operational completion/payment evidence, hosted storage and provider reconciliation still require their later release work. No project is certified financially or operationally complete by a fictional test.

Original migration-input requests are superseded by the owner's no-legacy-migration decision. Asset receipt is established; do not ask the owner to supply the same PDFs/artwork again merely because the historical external register said they were missing.

## Recommended next work

1. **Refresh the backup**, including the current database, private templates and exact code revision, before changing audit/database structures. Keep the previously verified backup separately.
2. **Complete RV-M01 and the project decision-history part of RV-M06.** This extends existing audit controls and preserves the owner's 167 events; it does not require inventing pricing or granting broader permissions. Do not retrospectively claim historical roles/sources that were never captured.
3. Fix RV-M04, close RV-M05 and expose approval metadata. Reconcile RV-M02 against a recorded role/assignment matrix.
4. Close RV-M03 with approved invoice-line representation and reconcile the scope-selection clarification. Run targeted tests, then the complete updated regression/browser suite and owner checks.
5. Record requirements-complete foundation acceptance. Then address the separate identity, configuration, hosting, template, recovery and operational release prerequisites.

**Recommendation:** continue local testing, starting with a fresh backup and audit completeness. Do not label the current build a finished operational MVP or deploy it for live business use on the basis of the present screen checks alone.

## Source references and code evidence

- [MVP §§2–12 and completion definition](https://github.com/447S18ht2h21U/Sighthillgecc1/blob/039e6fd8982a4cdc45af1aaf3305b3b4b9bda8f3/GECC-Minimum-Viable-Product.html)
- [Requirements Baseline: IR decisions and R-003/005/006/007/009/010/013/030/031/032/036](https://github.com/447S18ht2h21U/Sighthillgecc1/blob/039e6fd8982a4cdc45af1aaf3305b3b4b9bda8f3/GECC-Requirements-Baseline-v1.html)
- [External Input Lock Register: template mappings/issues](https://github.com/447S18ht2h21U/Sighthillgecc1/blob/039e6fd8982a4cdc45af1aaf3305b3b4b9bda8f3/GECC-External-Input-Lock-Register-v1.html)
- [Consolidated master specification](https://github.com/447S18ht2h21U/Sighthillgecc1/blob/039e6fd8982a4cdc45af1aaf3305b3b4b9bda8f3/GECC-master-project-final.html)
- [Historical project map](https://github.com/447S18ht2h21U/Sighthillgecc1/blob/039e6fd8982a4cdc45af1aaf3305b3b4b9bda8f3/GECC-master-project-map.html)
- [Detailed Sprint bundle, particularly 02–07](https://github.com/447S18ht2h21U/Sighthillgecc1/blob/039e6fd8982a4cdc45af1aaf3305b3b4b9bda8f3/GECC-master-project-sections-00-thru-16.html)
- [Implementation architecture and controlled owner amendments](GECC-Implementation-Architecture-v1.2.html), particularly REC-01, ADR-08/09, §§5/7/9/10.
- Implementation evidence at the reviewed code revision: `backend/core/models.py`, `services.py`, `api.py`, `auth.py`, `documents.py`, `management/commands/verify_audit.py`; `backend/config/settings.py`; `frontend/src/main.tsx`, `ProjectBrowser.tsx`, `AuditHistory.tsx`; corresponding tests and `frontend/tests/screen-review.mjs`.

This is a readiness finding report and acceptance-evidence record. It does not amend approved requirements, approve production clauses or authorize production sending/deployment.
