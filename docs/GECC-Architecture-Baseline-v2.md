# GECC Architecture Baseline v2

**Status:** Draft - architecture reconciliation
**Date:** October 10, 2026
**Supersedes:** No existing document  
**Business authority:** GECC Business Owner / Comptroller

## 1. Purpose and document control

This document extends the approved GECC requirements and implementation architecture without modifying their historical content.

Authoritative predecessor documents:
- `GECC-Requirements-Baseline-v1.html`
- `docs/GECC-Implementation-Architecture-v1.2.html`

Later explicit business-owner decisions govern their affected subjects. Historical decisions remain traceable.

This document does not certify production readiness.

## 2. Requirements reconciliation

Preserve IR-001 through IR-016 and R-001 through R-036 as historical identifiers.

Record subsequent approved amendments, including:
- Five calendar days after the later customer contract or invoice signature, subject to applicable cancellation and rescission requirements.
- Retention of the 50% deposit option, subject to legal applicability validation.
- Contractor payment processing and employee payroll/reporting.
- Separate installation-progress and payment-status dimensions.
- Comprehensive role-, record-, field-, and action-level authorization.

### 2.1 Historical requirements reconciliation

The original Requirements Baseline v1 contains IR-001 through IR-016 and R-001 through R-036. These identifiers and their historical approval records remain authoritative unless affected by a later explicitly approved amendment.

- IR-001 and R-007: The Sales Manager or Comptroller approves commercial Master Sales Record versions. The Installation Manager approves installation-related operational costs under IR-001 and R-008. New financial separation-of-duties requirements must be reconciled without silently removing these authorities.
- IR-003, R-025, and R-026: Financial statements use cash-basis reporting. Accounts receivable and accounts payable remain operational subledgers. Posted double-entry accounting transactions must balance and use approved accounts.
- Approved accounting amendment (October 10, 2026): GECC approved accrual accounting for company financial statements, superseding the original cash-basis financial-statement requirement in IR-003, R-025, and R-026 to that extent. A separate cash-basis receipts-and-disbursements reporting view remains required. The historical requirement remains preserved for traceability. Section 8.9 defines the approved target accounting policy, including revenue and expense recognition, customer deposits, payroll, commissions, and prevention of duplicate expense recognition. Production adoption requires accountant validation and successful regression testing.
- IR-004 and R-015: The original three-calendar-day installation waiting rule was subsequently amended to five calendar days after the later customer contract or invoice signature, subject to applicable cancellation and rescission requirements and legal validation.
- IR-005 and R-016: The customer signs the contract and invoice before the authorized GECC signer. Required signature sequencing must be enforced and auditable.
- IR-006 and R-017: The Installation Manager signs the completion certificate. The Comptroller may substitute when an approved exception reason is recorded. Required customer and GECC signatures must be verified.
- IR-007 and R-019 through R-020: Payment verification requires method, amount, date, project allocation, supporting evidence, and verifying user. Required payment verification remains a prerequisite to the applicable final project completion state.
- IR-008 through IR-012 and R-021 through R-028: Project deductions, fixed compensation, earned commissions, immutable calculation snapshots, locked reporting periods, and formal adjustment entries remain required.
- IR-013 and R-004: The original contractor-only terminology was subsequently amended by explicit business approval to include both employees and contractors. Payroll and contractor payment processing require separate, appropriate treatment.
- IR-014 and R-012: Canceled project codes are never reused. Authorized reopening retains complete historical records.
- IR-015 and R-018: Signature requests expire after 75 days. Renewal or reissue requires authorization and an auditable record.
- IR-016 and R-029: Monthly financial reports are prepared on the fifth calendar day of the following month. Weekend, holiday, timezone, and late-entry rules remain controlled configuration decisions.
- R-030 through R-031: Audit events and integrity controls must prevent undetected modification or deletion.
- R-032 through R-034: Approved document templates, role-relevant notifications, and reconciled data migration remain required.
- R-035: Inventory movements, serial numbers, FIFO costing, assets, depreciation, and loans must reconcile to project and accounting records.
- R-036: Production release remains blocked until acceptance testing, migration reconciliation, backup validation, training, and handover requirements are satisfied.

The historical source documents shall not be rewritten to incorporate later decisions. Approved amendments must identify the affected requirement, decision authority, effective date, and implementation impact.

## 3. Existing implementation and verification status

Implementation status in this section distinguishes source code identified, behavior inspected, automated tests defined, tests executed, and production verification. The presence of a model, service, or test does not independently establish that the requirement is satisfied.

### 3.1 Project dashboard - implementation assessment

Source files inspected:
- backend/core/dashboard_services.py
- backend/core/test_dashboard.py
- backend/core/test_dashboard_permissions.py

A repository search of backend/config/urls.py, backend/core, and frontend/src identified dashboard references only in the dashboard service and its two test modules. No dashboard API route, frontend component, or Customers & Projects navigation integration was identified in the searched source files.

Existing implementation:
- All six approved dashboard headings are defined.
- Sales Managers, Installation Managers, and the Comptroller receive all-project querysets.
- Sales Associates receive projects assigned to them.
- Technical Associates receive projects with an active technical assignment.
- Automated tests are defined for stage classification and these project-visibility rules.

Identified differences from approved requirements:
- Completed Customer Record is the default classification without demonstrated validation of all required customer and project data.
- Contracted for Work and Invoice Signed rely on document existence rather than verified signatures.
- Installation Complete relies on completion-certificate document existence rather than verified signatures and operational completion evidence.
- A verified payment replaces the installation-progress stage instead of remaining an independent payment-status dimension.
- A verified deposit and verified full payment are not distinguished in dashboard classification.
- The existing stage tests assert document-generation and payment-displacement behavior that conflicts with the subsequently approved dashboard requirements.

Required follow-up:
- Preserve authorized project scoping and extend it to all dashboard API responses, counts, drill-downs, and project details.
- Verify required customer data, signature evidence, scheduling prerequisites, and completion evidence before stage advancement.
- Separate installation-progress classification from verified deposit, partial-payment, and full-payment status.
- Implement and verify a role-authorized API endpoint and accessible frontend dashboard linked from Customers & Projects.
- Update conflicting tests and add negative authorization, signature-evidence, incomplete-record, payment-independence, and financial-information disclosure tests.
- Execute the relevant automated tests and record their results before classifying this functionality as verified.

Status: PARTIALLY IMPLEMENTED. Source inspected; automated tests identified but not executed during this review. Dashboard API and frontend integration not identified in the searched source.

### 3.2 Financial calculations and commission controls - implementation assessment

Source files inspected:
- backend/core/profitability_services.py
- backend/core/commission_services.py
- backend/core/commission_eligibility_services.py
- backend/core/commission_record_services.py
- backend/core/commission_report_services.py
- backend/core/test_profitability.py
- backend/core/test_commission.py
- backend/core/test_commission_eligibility.py
- backend/core/test_commission_records.py
- backend/core/test_commission_reports.py
- backend/core/api.py (targeted authorization-reference search)

Existing implementation:
- Gross profit uses the current approved MSR invoice amount and the latest approved cost record associated with that MSR.
- Seven project-cost fields are deducted: equipment, materials, dealer fee, lead, technician, Damon, and Jerry.
- Ryan and Doug variable commissions use 15% and 5% of positive gross profit, respectively.
- Negative gross profit is retained, with no Ryan or Doug variable commission on nonpositive gross profit.
- Commission eligibility checks verified full payment after approved adjustments and integrity-checked work-completion evidence.
- Commission-record creation invokes the eligibility service before calculating and creating draft records.
- Commission records and biweekly commission reports support approval, audit events, and stored calculation snapshots.
- Tests are defined for profitability prerequisites, commission calculations, eligibility, report creation, duplicate periods, and approved-record immutability.

Identified gaps and discrepancies:
- The Sales Associate's approved 50% share of net profit and GECC's remaining allocation are not calculated in the inspected commission services.
- Monetary quantize operations do not explicitly specify ROUND_HALF_UP, as required by approved financial policy.
- Ryan and Doug commission records both use project.sales_associate as recipient; recipient mapping requires correction or documented business confirmation.
- Commission-record creation and commission-report creation and approval contain no visible actor authorization check.
- Commission-record approval calls authorize(actor, project, approval=True), but the inspected services do not establish the required Comptroller-inclusive two-person financial approval process.
- Commission eligibility does not explicitly verify a signed completion certificate; work-completion evidence is checked separately.
- Commission creation is eligibility-gated, but all downstream payment and disbursement controls remain to be inspected.
- test_commission.py defines test_calculates_positive_profit_commissions twice; the later definition shadows the earlier definition.
- Dedicated negative authorization, recipient-mapping, 50% allocation, explicit rounding, and dual-approval tests were not identified in the targeted inspection.
- No direct references to the inspected commission functions were identified in backend/core/api.py; their complete invocation and exposure paths remain unverified.

Required follow-up:
- Implement and independently test the complete approved profit-allocation formula, including Sales Associate and GECC shares.
- Apply explicit ROUND_HALF_UP at approved monetary rounding boundaries.
- Resolve commission recipients and distinguish employee, contractor, and company allocations appropriately.
- Enforce actor authorization within each sensitive financial service and its eventual API entry points.
- Implement the approved two-person financial approval workflow with mandatory Comptroller participation, separation of duties, and auditable decisions.
- Confirm completion-certificate signature requirements and enforce all commission payment eligibility conditions.
- Review cost-record approval and defaults, downstream disbursement, payroll integration, and financial-report reconciliation.
- Add missing regression tests, correct the duplicate test method, execute the test suite, and record results.

Status: PARTIALLY IMPLEMENTED. Services inspected and automated tests identified, but tests were not executed during this review. Financial authorization and approved profit-allocation controls require further work.

### 3.3 Financial reporting and payroll - implementation assessment

Assessment basis: Source-code inspection of backend/core/financial_report_services.py, payroll_summary_services.py, employee_payroll_services.py, employee_project_allocation_services.py, contractor_payment_services.py, and contractor_services.py, as reviewed in October 2026. Findings describe observed service-level implementation, not verified runtime behavior. Model constraints, API-level authorization, integrations, and existing regression tests were not fully assessed. No application code, migrations, or tests were modified during this assessment.

#### 3.3.1 Company income statement

Observed: create_income_statement derives revenue from approved Master Sales Record snapshot total_price amounts using approval dates rather than verified satisfaction of contractual performance obligations. Project direct costs are drawn from approved cost records using approval dates. Contractor and employee expenses use paid records and payment dates, while commissions use approved records and approval dates. Employee expense is calculated using net payroll payments rather than gross wages and applicable employer costs.

Gap: The service mixes recognition bases and may report invoiced amounts as earned revenue. Project direct costs can overlap with contractor or employee expenses, creating potential duplicate deductions. The service does not demonstrate a reconciled accrual ledger or consistent period cutoffs.

Required remediation: Implement accountant-approved revenue and expense recognition events, accounts receivable, payables and accruals, consistent reporting-period cutoffs, gross employee compensation and employer costs, and source-level deduplication. Preserve approved GECC project profitability rules separately from statutory company financial statements.

#### 3.3.2 Balance sheet

Observed: create_balance_sheet calculates cash from verified customer receipts through the reporting date without subtracting outgoing payments or reconciling an opening cash balance. Contractor and employee liabilities are derived from approved records without a demonstrated as-of-date filter. The reviewed service does not establish complete receivables, customer deposit liabilities, equity, or other required balance-sheet accounts.

Gap: Reported cash may be overstated and the resulting output does not demonstrate a complete balanced statement of financial position.

Required remediation: Use reconciled cash accounts and as-of-date balances; include appropriate receivables, deposits, payables, payroll and commission liabilities, other assets and liabilities, and equity; enforce Assets = Liabilities + Equity.

#### 3.3.3 Cash flow statement

Observed: create_cash_flow_statement uses verified customer receipt dates and paid contractor and employee payment dates. It also includes approved commissions by approval date as cash outflows without demonstrated payment evidence. Other cash categories and opening-to-closing cash reconciliation are not established by the reviewed service.

Gap: Approved but unpaid commissions may be incorrectly represented as cash disbursements, and the report may omit other actual cash movements.

Required remediation: Recognize only verified cash transactions as receipts or disbursements; distinguish approval, liability recognition, and settlement; reconcile to cash balances and classify activities appropriately.

#### 3.3.4 Project profitability

Observed: create_project_profitability_report uses the current approved Master Sales Record total_price as revenue and sums approved project cost records. It additionally subtracts paid contractor payments, employee allocations calculated from paid net payroll amounts, and approved commissions. The resulting gross_margin calculation differs from the approved Gross Profit and allocation sequence in Section 8.2.

Observed risk: Approved cost records across multiple versions may be accumulated, and compensation may be counted both as a project direct cost and as a separate payment or allocation. Employee payroll amounts are not consistently scoped to the relevant reporting period. The report uniqueness check is based on report kind and project creation date, without demonstrated project scoping, so projects created on the same date may conflict.

Required remediation: Implement the approved seven-category Gross Profit formula and Ryan, Doug, Sales Associate, and GECC allocation sequence; select applicable approved cost versions; prevent duplicate deductions; apply appropriate period and project filters; and enforce project-specific report identity.

#### 3.3.5 Employee payroll, contractor payments, and payroll summaries

Observed: Employee payroll draft creation requires an approved compensation plan and nonnegative gross and net amounts, but the reviewed service does not demonstrate gross-minus-deductions-equals-net validation or independent payment evidence. Contractor payment drafts require approved compensation plans and nonnegative final amounts, but the reviewed service does not demonstrate full basis-and-deduction reconciliation or verified disbursement evidence.

Observed: create_payroll_summary totals paid contractor final amounts and paid employee net amounts within the payment-date period. This is a cash-disbursement-oriented summary, not a complete accrual employee and contractor compensation expense statement. Employee project allocations are approved without demonstrated service-level aggregate allocation validation.

Required remediation: Maintain separate employee and contractor obligations, gross compensation, deductions, employer payroll costs, net payments, effective compensation plans, payment evidence, and project allocation controls. Label cash-disbursement summaries accurately and reconcile them to accrual accounting statements.

#### 3.3.6 Authorization, approval, and audit

Observed: Contractor onboarding and compensation-plan functions include Comptroller role checks. The reviewed financial report creation and approval services, payroll summary approval, employee payroll approval, contractor payment approval, and related payment transitions do not consistently demonstrate equivalent service-level authorization or two distinct approving individuals. Several functions retain audit records and snapshots.

Gap: A single service-level approval does not by itself establish the approved two-person financial authorization rule. Additional model, API, and integration controls require inspection before any system-wide authorization conclusion.

Required remediation: Enforce applicable role and record authorization at every entry point, require Comptroller plus a second distinct authorized individual for designated financial actions, bind approvals to immutable snapshots, and preserve audit evidence. Require verified disbursement evidence before marking obligations paid.

#### 3.3.7 Production readiness and verification

Status: NOT VERIFIED FOR PRODUCTION. These findings are based on code reading; identified tests were not executed as part of this assessment. Existing tests and model/API controls may provide protections not visible in the reviewed service functions.

Before production: Reconcile implementation with Sections 3.2, 8.2, and 8.9; obtain GECC accountant review and approval of the accounting policy; define the account mapping and recognition-event model; correct identified service-level gaps; inspect model and API protections; implement or extend regression coverage for duplicate costs, accrual cutoffs, deposits, payroll liabilities, commissions, cash settlement, report scoping, financial permissions, and distinct-person approvals; then execute and document the tests.

## 4. Architecture and deployment controls

Preserve ADR-01 through ADR-09 from Implementation Architecture v1.2, including recovery objectives and outstanding verification requirements.

### 4.1 Approved technology and deployment decisions

Source: GECC Implementation Architecture v1.2, ADR-01 through ADR-09. These are approved architecture decisions, not evidence that production infrastructure has been deployed, configured, or tested.

ADR-01 - Application: Use React and TypeScript for the user interface, Django and Django REST Framework for the application API, and PostgreSQL as the authoritative relational database. Apply server-side authorization, relational transactions, decimal financial calculations, and pinned supported dependency versions.

ADR-02 - Hosting: Use AWS us-east-1, ECS Fargate, Application Load Balancer, ECR, and private networking. Run at least two application tasks across two availability zones with redundant background workers. The production database shall not have a public endpoint. Separate development, test/UAT, and production accounts or strongly isolated environments.

ADR-03 - Database: Use Amazon RDS for PostgreSQL with a Multi-AZ DB instance deployment and RDS Proxy. This selection is specifically a Multi-AZ DB instance, not a Multi-AZ DB cluster. Preserve UUID internal identifiers, unique project-code sequencing, decimal monetary amounts, UTC timestamps, and Eastern business dates.

ADR-04 - Search and dashboard: Use PostgreSQL full-text search with GIN indexes and indexed exact filters, together with React role-based dashboards. Apply authorization before search, counts, aggregation, or export. Search indexes shall be rebuildable. Dashboard tasks expose state, next action, owner, due date, and blocking reason. Refresh initially every 30 seconds and immediately after user actions, without extending the session idle timeout.

ADR-05 - Jobs and integrations: Use a transactional database outbox, Amazon SQS, redundant ECS workers, and EventBridge Scheduler. Commit business changes, audit events, and outbox records atomically. Require idempotency keys, retry controls, dead-letter handling, and visible reconciliation of uncertain outcomes. SQS is a delivery mechanism, not the authoritative record of pending work.

ADR-06 - Documents: Google Drive associated with the approved GECC business mailbox remains the business document destination. Store protected encrypted copies in Amazon S3 for recovery and retention. The database owns document metadata, versions, permissions, and source identity. Preserve originals, rendered PDFs, and signature certificates. The S3 preservation layer does not replace the selected business document service.

ADR-07 - Signatures and email: Integrate Docusign eSignature API and Connect, together with Gmail API OAuth for the approved GECC mailbox. Enforce ordered signing, authenticated callbacks, document and request hashes, exact-version matching, and reconciliation polling. Do not embed mailbox passwords in application code or represent provider-delivered invitations as necessarily originating from the Gmail address.

ADR-08 - Identity and secrets: Use Amazon Cognito with password authentication and SMS MFA, AWS Secrets Manager, KMS, and IAM workload roles. Enforce passwords of at least 12 characters containing letters, numbers, and special characters, subject to validated policy. Enforce the 30-minute idle timeout on the server; background polling must not reset it. The Comptroller controls accounts and role assignments. Protect provider credentials, refresh tokens, and webhook secrets.

ADR-09 - Operations: Use CloudWatch logs, metrics, alarms, and synthetic checks; CloudTrail; AWS Backup; infrastructure as code; and GitHub Actions with short-lived AWS OIDC deployment credentials. Maintain immutable build images, compatible schema migrations, and rolling or blue-green deployments. Critical incident notifications must reach the Comptroller through a channel independent of the application dashboard.

### 4.2 Transaction integrity and external-service boundaries

Use one authoritative PostgreSQL database and shared versioned domain rules across application and background workers. Do not distribute financial authority among independent services.

Each state-changing command must authorize the actor, validate state-transition guards, check or lock the current entity version, and atomically commit business changes, audit evidence, and outbox events. Duplicate submissions must return the original result rather than create duplicate financial or operational records. Competing approvals must not create multiple current versions.

Perform external-provider calls outside database transactions. Persist durable intent, idempotency identifiers, and reconciliation evidence. When a provider response is uncertain, reconcile the original request before retrying or reporting success.

Document states follow REQUESTED, RENDERED, PRESERVED, and READY. Verify the encrypted recovery copy and checksum before marking preservation complete. Retain the Drive file identifier and provider version. Signing and issuance require the exact READY document version.

### 4.3 Approved recovery objectives and limitations

GECC's approved Recovery Point Objective is zero acknowledged-data loss (RPO = 0). The approved Recovery Time Objective is no more than 15 minutes of service downtime (RTO <= 15 minutes). These requirements remain unchanged and are not automatically satisfied by selecting high-availability infrastructure.

For application-task or single-zone failure, redundant tasks, load balancing, synchronous database standby, and durable storage are the selected protections. Demonstrate preservation of acknowledged commits and end-to-end recovery within 15 minutes, including authentication, reads, writes, and document access.

For faulty deployments, retain immutable prior application images, use compatible database migrations, conduct smoke checks, and perform safe rollback. Rolling back application code must not discard valid transactions or audit history.

For logical corruption or account compromise, use point-in-time recovery, protected historical snapshots, independently protected backups, and reconciliation of later valid events. Database replication can also replicate corruption; PITR alone does not prove zero loss or 15-minute recovery.

For whole-region failure, cross-region snapshots, log copies, protected document replicas, and predeclared recovery infrastructure are proposed protections. Asynchronous replication does not establish RPO = 0. The source explicitly identifies regional-disaster design, costing, and proof of recovery coverage as unresolved work under OD-09.

For Google Drive, Gmail, SMS, or Docusign outages, preserve queued work, use available file recovery copies, and reconcile provider results. Do not fabricate successful signatures, notifications, authentication, or payments. AWS database high availability alone cannot guarantee end-to-end recovery of unavailable third-party services.

### 4.4 Backup, retention, and restoration testing

Enable RDS point-in-time recovery with a proposed 35-day rolling recovery window and separately retained daily snapshots. Schedule the business end-of-day backup at 00:15 America/New_York for the preceding business date. Record the business date and actual backup completion timestamp.

Protected daily archives must cover the database, documents, templates and artwork, approved configuration, audit records and anchors, notification and integration history, and a checksum manifest. Expiration of the rolling PITR window must not delete independently retained business history.

Preserve business history indefinitely under the approved policy, with no authorized permanent-delete workflow. Use S3 Object Lock, protected backup vaults, restricted retention and legal-hold administration, and monitoring of encryption-key availability. Legal holds and technical retention controls require ongoing governance; they are not mathematically irreversible.

Conduct an isolated restoration test on the last Sunday of each month at 03:00 America/New_York. Disable live email and signature delivery from restored data. Verify record counts, relationships, document checksums, signatures, audit anchors, ledger balances, historical reports, role access, and configuration versions. Preserve measured recovery timings and test evidence.

### 4.5 Incident response and production verification

Infrastructure failover may be preauthorized through controlled automation. Destructive restoration and business-data reconciliation require Comptroller incident authority.

Measure recovery from the start of actual service unavailability, not from the start of operator intervention. Alert immediately, target technical intervention within five minutes, and reserve the remaining recovery window for restoration and validation. Appoint a technical responder and backup owner with coverage appropriate to the recovery requirements.

Production readiness requires evidence from application and database failover drills, isolated restores, transaction and audit reconciliation, document recovery, access verification, and provider-outage handling. Record measured RPO and RTO outcomes for each tested failure scenario.

The selected architecture does not currently prove universal RPO = 0 and RTO <= 15 minutes, particularly for regional disasters, logical corruption, and external-service outages. Do not declare those objectives achieved without the required evidence. Preserve unresolved design, cost, staffing, and recovery-coverage questions as explicit release gates.

## 5. Role and permission matrix

To define authorization separately for project visibility, commercial records, documents, payments, commissions, payroll, and company financial reporting.

### 5.1 Authorization principles

GECC shall support configurable roles and granular permissions as the business expands.

Authorization shall distinguish:
1. Project and record visibility.
2. Field-level information visibility.
3. Action and approval authority.

Permissions shall be evaluated server-side for every API request, search, export, document retrieval, dashboard summary, and background operation.

New roles and permissions shall default to denied until explicitly approved and assigned.

### 5.2 Approved financial access

| Role | Project visibility | Financial information |
|---|---|---|
| CEO | All projects | Full authorized project and company financial information |
| Comptroller | All projects | Full authorized project and company financial information |
| Sales Manager | All projects in dashboard | Installation costs and authorized compensation information |
| Installation Manager | All projects in dashboard | Installation costs and authorized compensation information |
| Sales Associate | Assigned projects | Own sales and commission information |
| Technical Associate | Assigned projects | Own work and commission information |
| Accounts Payable Associate | Duty-specific records | Authorized payable amounts and supporting evidence |
| Database Administrator | Technical maintenance scope | No routine business financial access |

Project visibility does not imply access to all project fields.

### 5.3 Two-person financial authorization

Where GECC requires two-person financial authorization:
- The Comptroller is a required approver.
- The second approver must be a different authorized individual.
- Multiple roles held by one person do not satisfy the two-person requirement.
- Approvals must reference the exact transaction, payable, exception, or report version.
- Material changes invalidate approvals where required by the applicable workflow.

The CEO role provides broad financial visibility but does not automatically replace the Comptroller or bypass established approval requirements.

### 5.4 Expandable role management

The authorization architecture shall support:
- Creation of additional roles.
- Explicitly approved multiple-role assignments.
- Resource-, action-, field-, and project-scope permissions.
- Controlled role creation, modification, assignment, and revocation.
- Effective-dated, auditable permission changes.
- Prevention of self-escalation and unauthorized delegation.
- Separation-of-duties enforcement based on distinct user identities.
- Regression tests against unauthorized financial disclosure.

Role and permission administration shall require specifically authorized administrators and an auditable approval process. The exact administrative approval matrix remains to be specified.

### 5.5 Compatibility and migration safeguards

The seven existing Django role identifiers shall remain supported during migration.

The existing User.role field, commercial project_scope(), customer_scope(), permitted(), and authorize() behavior shall not be removed or broadened without an approved migration and regression tests.

Introduce centralized, purpose-specific authorization policies incrementally.

The new dashboard shall use a separate authorized project queryset and restricted, role-aware serializers. It shall not expose commercial MSR snapshots merely because a user may see a project in the dashboard.

Dashboard counts, totals, aging, and project lists shall be calculated only after applying the requesting user's record-scope restrictions.

Existing security controls and automated tests shall be preserved. Additional tests shall verify API responses, sensitive-field exclusions, approval separation, and configurable-role default-deny behavior.

## 6. Master Sales Record and operational records

Preserve approved MSR immutability, version history, audit controls, and separate operational equipment, installation, and warranty records.

### 6.1 Master Sales Record authority and immutability

Source: GECC Implementation Architecture v1.2, REC-02, REC-03, OD-05, lifecycle section 6.3, and verification V-02.

The Master Sales Record (MSR) is the authoritative approved commercial snapshot for a project. An authorized preparer may edit a draft subject to role permissions and validation. Submission freezes that draft for approval review. Approval freezes every field of the exact submitted version.

Approved MSR records shall not be updated or deleted. This includes customer details, contact and address information, work types, scope, equipment selections, prices, payment terms, and commercial costs. An edit to the current customer master record shall not silently change an approved MSR snapshot.

Every correction to an approved MSR field requires a new controlled version, regardless of whether the change is commercial or administrative. No exception is inferred for minor corrections. Preserve prior approved versions, their approvals, source evidence, documents, calculations, and audit history.

### 6.2 Draft, submission, rejection, and approval

An authorized preparer may submit a draft only when required customer, address, contact, scope, equipment, pricing, and payment information is valid; an assigned owner and project code exist; and unresolved duplicate warnings have been addressed.

Submission creates an identifiable frozen review version, an approval task, and the required alert. Approval or rejection must target the exact current submitted version.

A Sales Manager or Comptroller may approve or reject an MSR submission within the approved authorization policy. Apply applicable separation between preparation and approval.

A rejection requires a reason and preserves the rejected submission and audit record. Corrections return the proposal to draft and must pass submission validation again. Approval creates an immutable version and the applicable document-generation tasks.

Production signing requires the exact approved MSR, approved production-ready templates, preserved READY documents, and ordered signer identities. Generating unsigned MVP documents does not establish production signing readiness.

### 6.3 Controlled MSR revisions

A proposed revision shall record the fields to change, the reason, supporting evidence, anticipated impact, preparer, and applicable approval history.

Create a new numbered draft from the last approved MSR without overwriting the approved snapshot. The currently approved version remains authoritative while the revision is pending. Revision states include DRAFT, SUBMITTED, APPROVED, and REJECTED, with permitted transitions and validation controls.

Changes to work type, scope, price, payment terms, commercial costs, or any other frozen field require this controlled revision process. Preserve prior version identifiers, timestamps, documents, calculations, and audit evidence.

When changed scope is proposed, pause affected installation work immediately while the commercial impact is reviewed. Rejection permits resumption only within the original approved scope and subject to all other applicable guards.

Approval of a revision does not itself authorize changed-scope installation. Regenerate affected documents, supersede active signature requests while retaining historical originals, obtain new required signatures, and recompute relevant commercial baselines and waiting-period, rescission, deposit, and scheduling gates. Resume only after all applicable checks pass.

A refund or retrospective financial correction after completed physical work follows the controlled adjustment process and does not automatically require re-signing already completed work.

### 6.4 Separate operational records

Operational facts shall be stored as linked append-only records rather than edits to the approved MSR. These include equipment serial numbers, installation photographs, technician notes, actual materials consumed, work tasks, scheduling and installation events, payment events, signature events, and relevant warranty evidence.

Maintain clear references from each operational record to its project, source or MSR version where applicable, actor, timestamp, and supporting evidence. Preserve correction and supersession history rather than overwriting prior events.

The current project view may combine the approved commercial MSR with later operational records, but that combined presentation shall not modify or replace the approved MSR snapshot.

Equipment, installation, and warranty records shall distinguish the approved commercial equipment selection from actual equipment installed and manufacturer-specific warranty applicability. Material differences requiring a commercial change shall enter the MSR revision process rather than being silently incorporated into the approved snapshot.

### 6.5 Holds, cancellation, and reopening

A hold shall preserve the previous project phase together with its reason, linked proposal or incident, approver, and evidence. Holds may arise from scope review, expired signatures, unresolved payment adjustments, document conflicts, or data-integrity failures.

Clear only the specific resolved hold. Releasing one hold must not bypass another active restriction, applicable legal rescission requirements, or immutable-history controls.

A Sales Manager, Installation Manager, or Comptroller may request cancellation. Execution requires authorization by a Sales Manager or Comptroller under the approved lifecycle rules.

Cancellation stops future work and active unsigned signature requests while preserving deposits, signatures, incurred costs, obligations, and historical evidence. Refunds and fees remain subject to their own authorization requirements. The canceled project code shall never be reused.

Reopening requires authorization and a recorded reason. Retain the original project identity and code, create controlled revision or correction records where necessary, and reevaluate affected prerequisites.

Preserve completed or closed financial snapshots and earned commission history. If later facts invalidate an entitlement, use linked adjustments rather than issuing an additional unlinked payment.

### 6.6 Integrity, authorization, and regression acceptance

Enforce immutability, version selection, and transition authorization at the service and persistence boundaries, not solely through frontend restrictions.

Concurrent submissions, approvals, and revisions shall not create multiple authoritative current approved versions. Record who performed each action, the exact affected version, timestamps, decisions, reasons, and related audit evidence.

Required regression coverage includes rejection of UPDATE and DELETE operations on approved MSR versions; confirmation that edits to customer master data do not change approved snapshots; successful authorized append of operational events; and preservation of earlier documents and financial calculation history through revisions.

Additional acceptance cases shall verify rejected submissions, competing approvals, changed-scope installation holds, re-signing requirements after affected revisions, cancellation code reservation, and controlled reopening without duplicate financial payments.

These controls are approved requirements. Their inclusion in this document does not establish that every safeguard is already implemented or tested.

## 7. Project lifecycle and dashboard

Retain the six approved dashboard headings. Installation progress and payment status are independent dimensions. Stage advancement requires verified evidence and applicable prerequisites.

Dashboard counts and project lists must be calculated only from records authorized for the requesting user.

### 7.1 Dashboard structure

The dashboard shall display six approved headings:
1. Completed Customer Record
2. Contracted for Work
3. Invoice Signed
4. Installation Scheduled
5. Installation Complete
6. Payment Received

Selecting a heading shall reveal the projects associated with that heading.

The dashboard shall be accessible from Customers & Projects to every role explicitly authorized for dashboard access.

### 7.2 Independent status dimensions

Installation progress and payment status shall be tracked independently.

A project may appear in one installation-progress stage and simultaneously in the Payment Received view.

A verified deposit shall not remove a project from its installation stage.

Payment Received shall distinguish:
- Verified deposit or partial payment.
- Verified payment in full.

Unverified payments shall not count as received.

Payment-in-full determination shall use verified payments and authorized adjustments against the applicable approved amount.

### 7.3 Installation-progress stage evidence

Completed Customer Record:
- All required customer and project information must be present and validated.
- Incomplete records shall not be counted as completed customer records.

Contracted for Work:
- The applicable contract must have verified required signatures.
- Generating an unsigned contract shall not advance the project.

Invoice Signed:
- The applicable invoice must have verified required signatures.
- Generating an unsigned invoice shall not advance the project.

Installation Scheduled:
- An authorized installation schedule must exist.
- Applicable signature, waiting-period, rescission, and deposit prerequisites must be satisfied before scheduling or work proceeds, according to the approved workflow.

Installation Complete:
- Required installation completion evidence and verified completion-certificate signatures must exist.
- Operational verification requirements shall be enforced.
- Installation completion shall remain distinct from final financial reconciliation and project closure.

Stage transitions shall retain their supporting evidence and audit history.

### 7.4 Role-scoped dashboard calculations

Dashboard project visibility:
- CEO: all projects.
- Comptroller: all projects.
- Sales Manager: all projects.
- Installation Manager: all projects.
- Sales Associate: assigned projects.
- Technical Associate: assigned projects with active applicable assignments.
- Other roles: only explicitly authorized dashboard scopes.

Every count, total, aging calculation, and project listing shall be derived from the requesting user's authorized project queryset.

Financial fields shall be independently restricted by role and permission.

Dashboard responses shall not expose full commercial Master Sales Record snapshots by default.

Canceled projects shall be excluded from active-stage counts while retaining their historical records.

### 7.5 Dashboard API and presentation

Provide a dedicated authenticated GET /api/dashboard/ endpoint.

Use purpose-specific authorization policies and role-aware response serializers.

Provide a dedicated frontend dashboard panel and ProjectDashboard.tsx component.

Support keyboard navigation, visible focus indicators, accessible controls, appropriate touch targets, and responsive Windows, iOS, and Android browser layouts.

Dashboard refresh shall preserve session-security requirements and shall not extend idle-session lifetime through background polling.

### 7.6 Required regression coverage

Preserve existing dashboard and security tests while extending coverage for:
- Incomplete customer information.
- Verified contract signatures.
- Unsigned contract exclusion.
- Verified invoice signatures.
- Unsigned invoice exclusion.
- Valid installation scheduling prerequisites.
- Signed completion certificate and operational prerequisites.
- Verified deposit without installation-stage displacement.
- Verified full payment distinguished from partial payment.
- Role-scoped project counts and listings.
- Restricted financial fields and absence of unauthorized MSR snapshots.
- Canceled-project exclusion from active counts.
- CEO and Comptroller financial visibility.
- Sales Manager financial restrictions.
- Default-deny behavior for future configurable roles.

## 8. Financial controls and reporting

Preserve approved profitability calculations, payment verification, commission eligibility, dual approvals, calculation snapshots, and locked reporting periods.

### 8.1 Financial record integrity

Financial calculations shall reference the applicable approved Master Sales Record version and authorized, auditable financial inputs. Subsequent commercial changes shall create a new approved version rather than altering the historical approved record.

### 8.2 Project profitability and allocation

Gross Profit = Approved Invoice Amount - Equipment Cost - Materials Cost - Dealer Fee - Lead Cost - Technician Cost - Damon Compensation - Jerry Compensation.

Ryan allocation = 15 percent of positive Gross Profit.
Doug allocation = 5 percent of positive Gross Profit.
Net Profit = Gross Profit - Ryan allocation - Doug allocation.
Sales Associate allocation = 50 percent of Net Profit.
GECC allocation = remaining Net Profit.

Preserve approved defaults of $500 for Damon and $250 for Jerry where applicable. Lead cost remains a variable project cost rather than an assumed fixed $3,000 charge.

Use decimal arithmetic and the approved half-up rounding convention to USD cents. Prevent duplicate deductions of compensation or project costs. Preserve negative profitability rather than artificially reporting zero profit; variable profit-based commissions are zero when Gross Profit is not positive.

Changes to these approved formulas or defaults require formal authorization, effective-dated configuration, and regression testing.

### 8.3 Payment verification and reconciliation

Maintain distinct records for invoiced amounts, authorized adjustments, deposits, partial payments, and final payment.

Only verified receipts count toward Payment Received. Payment in Full requires reconciliation of verified receipts and authorized adjustments against the applicable approved amount.

A deposit or partial payment shall not remove a project from its current installation-progress stage.

Retain source evidence, receipt dates, reconciliation history, and authorized corrections without silently rewriting historical financial records.

The approved 50 percent deposit option remains a business requirement subject to applicable Maryland legal validation before production use.

### 8.4 Employees, contractors, and compensation

Financial and payroll reporting shall cover both employees and contractors, while maintaining the appropriate distinction between employee payroll obligations and contractor payables.

Preserve the existing compensation and commission rules, including the conditions requiring verified full adjusted payment, completed work, approved costs, and required signatures before commission eligibility is finalized.

Prevent duplicate compensation obligations and duplicate cost deductions. Retain calculation inputs, applicable rates, approved adjustments, payee identity, classification, authorization evidence, and payment status.

Employee withholding, employer taxes, contractor reporting, and classification treatment require validated accounting and legal configuration; do not infer tax treatment solely from a GECC role name.

### 8.5 Financial visibility and least privilege

CEO and Comptroller may view all authorized project and company financial information.

Sales Manager and Installation Manager financial visibility is restricted to installation costs and authorized compensation information; access to all projects does not grant unrestricted company financial access.

Sales Associates and Technical Associates may view only their authorized assignments and their own authorized compensation or commissions, not unrelated customer payment amounts or company profitability.

Accounts Payable Associates receive only duty-specific authorized payable information. Database Administrators do not receive routine business financial visibility by virtue of technical privileges.

Apply field-level and record-level authorization independently to API responses, exports, reports, dashboards, and supporting documents. Default to denial for new or unconfigured roles.

### 8.6 Two-person financial authorization

Every financial action designated as requiring two-person authorization shall include approval by the Comptroller and by a second, distinct, appropriately authorized individual.

Two roles assigned to one person do not satisfy the two-person requirement. Approval evidence must identify both individuals, their authorization at approval time, the action, the record or report version, and the approval timestamps.

Approvals shall apply to the same transaction or report snapshot. Material changes after approval shall invalidate or require renewal of approvals as specified by the controlled workflow.

Existing specific approval responsibilities shall remain in effect unless explicitly amended. The precise second-approver matrix and treatment of exceptions must be reconciled with the new restricted Sales Manager financial visibility before implementation.

### 8.7 Reporting, locking, and audit

Provide authorized project profitability, compensation, contractor payable, employee payroll, and company financial reports with role-specific views and exports.

Retain reproducible calculation snapshots, effective-dated configuration versions, source references, approval history, and audit trails.

Locked reporting periods shall not be silently modified. Corrections must use authorized, traceable adjustment or reopening workflows, preserving the original historical state.
Only the Comptroller may initiate changes to configurable financial values, subject to required approval, dating, versioning, and audit controls.

### 8.8 Required financial regression coverage

Preserve all existing financial and security tests. Extend tests to cover calculation precision, negative profit, duplicate deduction prevention, payment verification, partial versus full payment, employee and contractor reporting, commission eligibility, restricted financial fields, project-scoped access, distinct-person approvals, snapshot invalidation, configuration effective dates, and reporting-period locks.

Production release remains gated on unresolved accounting configuration, applicable legal validation, authorized approver assignments, and evidence that sensitive financial information cannot leak through APIs, exports, or dashboards.

### 8.9 Accounting basis, recognition policy, and expense deduplication

Decision status: APPROVED by GECC for architecture design on 2026-10-10. Production adoption requires review and validation by GECC's accountant. This section defines the target policy; it does not certify that existing software implements it.

GECC company financial statements shall use accrual accounting. A separate cash-basis reporting view shall show actual verified receipts and disbursements. Project profitability, accounting income, liabilities, and cash flow must be distinguishable and reconcilable.

Revenue recognition: A signed contract, approved Master Sales Record, or issued invoice does not alone establish earned revenue. Recognize revenue when the applicable contractual performance obligation has been satisfied, ordinarily upon verified installation completion and required acceptance, subject to contract-specific obligations and accountant-approved treatment. Recognize earned but uncollected amounts as accounts receivable. Assess deposits, milestones, adjustments, refunds, and cancellation terms separately.

Customer deposits: Record verified advance receipts as cash and an appropriate customer deposit or contract liability until earned. Apply deposits against amounts due without recording revenue twice. Distinguish invoicing, earned revenue, customer receipts, receivables, and deferred revenue.

Expense recognition: Recognize equipment, materials, services, employee compensation, contractor compensation, and earned commissions when the relevant costs are incurred and obligations are established, using accountant-approved cutoffs. Do not recognize an expense solely because its invoice was approved or cash was disbursed. Recognize outstanding amounts as the appropriate payable, accrued expense, payroll liability, or commission liability.

Employee accounting: Recognize gross wages and applicable employer payroll costs when incurred. Separately track employee withholding, employer taxes, benefits, net disbursements, and outstanding payroll liabilities. Employee net pay alone must not be labeled total employer payroll expense.

Contractor accounting: Recognize eligible contractor service costs when incurred and determinable. Record outstanding contractor obligations separately from employee payroll liabilities. Settlement of a contractor payable reduces cash and the payable; it does not generate a second expense.

Commission accounting: Preserve GECC's approved commission eligibility and allocation rules. Recognize an earned, measurable commission obligation under the accountant-approved policy; distinguish eligibility, authorization, accrual, approval, and actual disbursement. Approval alone is not proof of cash payment.

Expense deduplication: Every recognized expense shall have a stable source identifier, expense classification, project association where applicable, and a traceable link to its corresponding obligation and settlement. An amount included in approved project direct costs shall not be deducted again as a contractor payment, employee allocation, or other operating expense. Financial statements and project reports shall derive overlapping amounts from a common reconciled expense source, not independently count the same cost twice.

Project profitability: Preserve the approved seven-category Gross Profit formula and the Ryan, Doug, Sales Associate, and GECC allocation rules in Section 8.2. Distinguish project Gross Profit, Net Profit after approved commissions, compensation allocations, and company operating profit. Apply the appropriate approved cost-record version; exclude superseded versions from cumulative expense totals. Do not assume a distribution to GECC is itself an additional operating expense.

Balance sheet: Calculate cash from reconciled opening balances plus verified receipts minus verified disbursements and other authorized cash movements. Include applicable receivables, customer deposits or contract liabilities, contractor and employee payables, commission liabilities, other assets and liabilities, and equity. Enforce reporting-date cutoffs and the accounting equation: Assets = Liabilities + Equity.

Cash flow: Include actual verified cash receipts and disbursements within the reporting period. Approved but unpaid commissions, payroll, contractor obligations, and other payables are not cash outflows. Reconcile cash-flow movements to cash accounts and distinguish operating, investing, and financing activity as applicable.

Reporting controls: Use consistent accounting periods, recognition dates, effective-dated configuration, Decimal arithmetic with approved USD rounding, immutable source references, audit history, and reproducible snapshots. Prevent duplicate journal entries and repeated recognition from superseded Master Sales Record or cost-record versions. Corrections shall use authorized reversing or adjusting entries; locked periods require a controlled reopening or later-period adjustment process.

Implementation and production gate: Existing income statement, balance sheet, cash flow, payroll, and project profitability services require reconciliation against this policy before production use. GECC's accountant must review recognition triggers, account classifications, treatment of deposits, commissions, employer payroll costs, expense capitalization, financial statement presentation, and tax-related configuration. Accountant approval and passing regression tests are required before this policy is operationally adopted.

## 9. Frontend and accessibility

Use a dedicated `dashboard` panel and `ProjectDashboard.tsx` component. Support responsive Windows, iOS, and Android browser layouts, keyboard accessibility, visible focus indicators, appropriate touch targets, and avoidance of horizontal scrolling.

### 9.1 Application navigation

Preserve the existing React and TypeScript frontend and its approved application workflows.

Provide a dedicated dashboard panel accessible from the Customers & Projects screen. Use a ProjectDashboard.tsx component integrated into the existing navigation architecture.

All authorized users shall be able to open the dashboard. Navigation visibility and project access shall follow the approved role and permission model.

### 9.2 Dashboard presentation

Display the six approved dashboard headings in the established business order.

Selecting a heading shall reveal the projects associated with that heading, subject to the requesting user's authorization.

Show verified deposits or partial payments separately from verified payment in full. Payment status shall not displace a project from its installation-progress stage.

Display loading, empty, error, and unauthorized states clearly. Do not imply that a missing or unverified business event has occurred.

### 9.3 Responsive layouts

Support current mainstream browsers on Windows 10 or later, iOS, and Android.

Use responsive layouts suitable for desktop, tablet, and phone viewports. Avoid horizontal page scrolling and clipped controls.

Tables and project detail views shall adapt to narrow screens without concealing essential workflow status or security information.

Provide touch targets and spacing appropriate for mobile interaction.

### 9.4 Accessibility and interaction

Support keyboard-only navigation throughout dashboard controls, project lists, dialogs, and forms.

Provide visible keyboard focus, meaningful accessible names, semantic headings, and correctly associated form labels.

Communicate validation errors and workflow status using text and accessible status messages rather than color alone.

Maintain readable text, sufficient contrast, predictable navigation, and usable zoom behavior.

Use accessible confirmation patterns for consequential actions, including approvals and financial operations.

### 9.5 Authorization and sensitive information

Frontend navigation and field visibility shall reflect server-authorized permissions, but the frontend shall never be the sole enforcement point.

The backend shall enforce project scope, action permissions, and financial field restrictions for every relevant API request.

Do not load unauthorized Master Sales Record snapshots or sensitive financial values into hidden interface components.

Dashboard counts, filters, exports, and detail links shall remain consistent with server-side authorization.

### 9.6 Session and refresh behavior

Preserve the approved authentication, multifactor authentication, and session-security architecture.

Maintain the approved 30-minute idle-session policy. Background dashboard polling shall not count as user activity or silently extend the idle-session lifetime.

Handle expired sessions and authorization failures safely without displaying stale sensitive data.

Refresh intervals shall be configurable within approved operational and security limits; the existing architecture specifies a 30-second dashboard refresh target.

### 9.7 Frontend regression and acceptance testing

Preserve existing frontend behavior and automated tests.

Extend coverage for dashboard navigation, six-stage presentation, independent payment status, role-scoped listings, restricted financial fields, keyboard operation, focus visibility, responsive layouts, loading and error states, and session expiration.

Validate representative Windows desktop, iOS, and Android browser experiences before production acceptance.

Frontend changes shall be implemented incrementally with corresponding backend authorization and regression tests.

## 10. Security and regression testing

Preserve all existing security controls and automated tests. Extend coverage for role-specific API responses, sensitive-field restrictions, dashboard stage evidence, and independent payment status.

### 10.1 Preservation of existing security controls

Preserve all existing authentication, authorization, database integrity, audit, document verification, and automated regression protections.

Architecture changes shall not remove, bypass, or weaken existing controls without a separately approved, documented replacement providing equivalent or stronger protection.

Retain the existing approved Master Sales Record immutability controls, database-level protections, and historical version records.

### 10.2 Authentication and session security

Preserve the approved production authentication architecture, including Cognito, multifactor authentication, protected credentials, and the 30-minute idle-session policy.

Require authenticated access to protected application functions and APIs.

Background polling, automatic refresh, and other noninteractive requests shall not silently extend idle-session lifetime.

Session expiration, account disablement, and permission revocation shall prevent continued access to protected information.

### 10.3 Authorization and project scope

Enforce authorization on the server for every protected resource, action, and sensitive field.

Preserve existing authorization behavior during controlled migration to expandable role management.

Support multiple authorized roles per individual without allowing privilege escalation or bypass of identity-based separation of duties.

Apply project-scope restrictions before calculating dashboard counts, totals, search results, or exports.

Use default-deny behavior for unrecognized roles, missing permissions, and unauthorized requests.

### 10.4 Financial information protection

Enforce the approved financial visibility restrictions independently of project visibility.

CEO and Comptroller financial access shall follow their approved authority.

Sales Manager and Installation Manager access shall remain restricted to installation costs and authorized compensation information.

Sales Associates and Technical Associates shall not receive unrelated customer payment information or company profitability data.

Protect sensitive financial information in API serializers, documents, exports, dashboard responses, application logs, and error messages.

### 10.5 Separation of duties and approvals

Enforce the approved two-person financial authorization requirements.

The Comptroller must participate in every financial authorization designated as requiring two approvals.

The second approver must be a different authorized individual.

Multiple roles assigned to one person shall not satisfy the distinct-person requirement.

Approval records shall identify the approving individuals, their authority, the applicable record version, and the approval timestamps.

Changes to approved financial records or report snapshots shall trigger the applicable reapproval requirements.

### 10.6 Database integrity and auditability

Preserve approved Master Sales Record version immutability and database-level enforcement.

Retain audit evidence for financial changes, role assignments, permission changes, approvals, payment verification, and project lifecycle transitions.

Use controlled, reversible migrations with documented compatibility checks and recovery procedures.

Historical records shall remain available for authorized review without permitting unauthorized modification.

### 10.7 Electronic signatures and integrations

Preserve the approved DocuSign integration architecture, including authenticated callbacks, verified account identity, and signature evidence.

Document existence alone shall not establish that required signatures have been completed.

Validate callback authenticity, expected account identity, document association, and required signature completion before advancing protected workflow states.

Protect integration credentials using approved secrets-management controls.

External integration failures shall not silently advance project or financial states.

### 10.8 Infrastructure and operational security

Preserve the approved AWS deployment, private networking, encryption, secrets management, monitoring, audit logging, backup, and recovery architecture.

Production access shall follow least-privilege IAM policies and separation of environments.

Maintain the approved zero-data-loss recovery objective and maximum 15-minute recovery-time objective as targets requiring demonstrated operational evidence.

Do not represent these recovery targets as achieved until supported by successful recovery and failover testing.

### 10.9 Security regression testing

Preserve all existing automated tests.

Extend coverage for authentication, idle-session expiration, role-scoped project access, sensitive-field exclusion, dashboard calculations, signature verification, Master Sales Record immutability, audit integrity, and financial approval separation.

Test unauthorized access through direct API requests, exports, alternate serializers, and changed role assignments.

Test negative cases, including missing signatures, incomplete customer records, unverified payments, revoked permissions, and attempted self-approval.

Security-related changes shall require passing regression tests and documented review before release.

### 10.10 Release acceptance and evidence

Maintain traceable evidence connecting approved requirements to implementation, tests, and release acceptance.

Record unresolved security exceptions, accountable owners, mitigation plans, and approval decisions.

Production deployment shall remain blocked when mandatory security, legal, accounting, signing, or recovery requirements lack required validation.

No architecture document approval alone constitutes evidence that an unimplemented control is operational.

## 11. Outstanding inputs and production release gates

Maintain explicit tracking of legal validation, accounting configuration, signing integration, infrastructure recovery evidence, and operational acceptance.

### 11.1 Release governance and evidence

Each production release gate shall identify its requirement, accountable owner, current status, supporting evidence, outstanding action, and approval authority.

A documented requirement is not evidence that the corresponding control has been implemented, tested, or accepted.

Unresolved mandatory release gates shall prevent production deployment unless an explicitly authorized exception is permitted by the applicable requirements and law.

### 11.2 Legal and regulatory validation

Obtain appropriate Maryland legal review of the approved five-calendar-day installation waiting rule, applicable rescission requirements, and the retained 50 percent deposit option.

Determine whether Maryland home improvement contract requirements or deposit restrictions apply to each relevant transaction and reconcile any conflicts before production use.

Validate contract, invoice, completion certificate, electronic signature, and required disclosure language.

Document legal conclusions, applicable conditions, responsible reviewers, and approval evidence.

Do not treat an approved business preference as proof of legal compliance.

### 11.3 Accounting and financial configuration

Complete and approve the chart of accounts, financial classifications, tax applicability, reporting periods, and reconciliation procedures.

Validate employee payroll obligations and contractor payable treatment, including applicable classification, withholding, tax, and reporting requirements.

Confirm the authorized second-approver matrix for financial actions, including payment exceptions, contractor payables, reports, and reporting-period corrections.

Reconcile any existing Sales Manager approval responsibilities with the newly approved restrictions on Sales Manager financial visibility.

Validate effective-dated financial configuration, approved compensation formulas, payment verification, and reporting-period controls.

### 11.4 DocuSign and document acceptance

Preserve the verified DocuSign sandbox account configuration and existing integration evidence.

Complete end-to-end testing of document generation, required GECC and customer signatures, callback authentication, document association, and signature-status verification.

Test financed and non-financed completion certificates and all required interactive document fields.

Confirm that unsigned, incomplete, incorrectly associated, or unverified documents cannot advance protected workflow stages.

Production credentials, account configuration, and callback endpoints require separate production verification.

### 11.5 Infrastructure, backup, and recovery

Complete the approved production infrastructure configuration, security review, monitoring, backup configuration, and deployment automation.

Demonstrate the approved zero-data-loss recovery objective and maximum 15-minute recovery-time objective through documented recovery and failover tests.

Verify recovery of application data, protected documents, audit records, and required integration state.

Record test dates, environments, procedures, observed recovery results, exceptions, and accountable approvals.

Recovery targets shall remain unverified until supported by satisfactory operational evidence.

### 11.6 Security and access acceptance

Complete role and permission acceptance for CEO, Comptroller, Sales Manager, Installation Manager, Sales Associate, Technical Associate, Accounts Payable Associate, Database Administrator, and future configurable roles.

Verify project-scoped access, financial field restrictions, separation of duties, approval identity, and default-deny behavior.

Validate session expiration, multifactor authentication, secrets protection, audit trails, and Master Sales Record immutability.

Require successful security regression testing and documented remediation of release-blocking findings.

### 11.7 Operational and user acceptance

Validate the six dashboard headings, supporting stage evidence, independent payment status, role-scoped project lists, and restricted financial presentation.

Confirm responsive operation and accessibility on representative Windows, iOS, and Android browsers.

Validate employee and contractor financial reporting, authorized approvals, installation workflows, customer records, and document generation.

Obtain acceptance from the designated business authorities for the applicable workflows and reports.

### 11.8 Release decision and outstanding-items register

Maintain a controlled register of outstanding requirements, decisions, dependencies, risks, owners, target dates, and evidence references.

Classify each item as approved and implemented, approved but not implemented, awaiting validation, blocked, or formally deferred.

Record the final release decision, its authorized approvers, the accepted software version, and the evidence reviewed.

Do not close an unresolved mandatory requirement solely because the architecture document is complete.

## 12. Implementation sequence and change history

Changes to approved requirements require a controlled amendment record. Implementation proceeds through reviewed, testable increments.

### 12.1 Change control and preservation

Preserve existing application functionality, database migrations, database integrity controls, security protections, and automated tests.

Do not replace existing role authorization, project-scoping, or Master Sales Record immutability mechanisms without an approved migration plan and equivalent or stronger verified controls.

Maintain a recoverable Git checkpoint before each implementation increment.

### 12.2 Implementation phase 1 - Baseline reconciliation

Review the existing requirements baseline, approved amendments, architecture decisions, application models, APIs, frontend components, and automated tests.

Identify implemented controls, partially implemented controls, missing capabilities, and conflicts requiring business decisions.

Record traceability between approved requirements, affected components, and required tests.

Do not treat proposed architecture as completed implementation.

### 12.3 Implementation phase 2 - Role and permission foundation

Introduce the approved CEO role and expandable role-management architecture through controlled, backward-compatible changes.

Preserve existing role identifiers and authorization behavior until replacement policies are implemented, tested, and approved.

Support multiple roles per individual while maintaining resource, action, field, and project-scope restrictions.

Enforce default-deny behavior, controlled role assignments, and identity-based separation of duties.

Verify that no existing user gains unauthorized project or financial access.

### 12.4 Implementation phase 3 - Dashboard and lifecycle controls

Implement the approved dashboard API and frontend navigation using authorized project scopes.

Correct stage evidence requirements for completed customer records, signed contracts, signed invoices, installation scheduling, and signed completion certificates.

Maintain installation progress independently from verified deposit, partial-payment, and full-payment status.

Preserve project history and exclude canceled projects from active-stage counts.

Extend existing dashboard and permission tests before accepting the changes.

### 12.5 Implementation phase 4 - Financial controls and reporting

Implement authorized financial views, project profitability, employee payroll reporting, contractor payables, and compensation reporting.

Preserve approved calculation formulas, rounding rules, commission eligibility, payment verification, and historical snapshots.

Implement the approved two-person authorization controls, requiring the Comptroller and a distinct authorized second individual.

Resolve the second-approver matrix and accounting configuration before activating affected production workflows.

Verify financial field restrictions across APIs, reports, exports, and dashboards.

### 12.6 Implementation phase 5 - Documents and operational workflows

Complete contract, invoice, and completion-certificate generation and verified signature workflows.

Support financed and non-financed completion certificates and required GECC signature fields.

Implement the approved installation waiting rule subject to completed legal validation.

Verify scheduling prerequisites, installation evidence, document association, and audit history.

Preserve existing DocuSign sandbox functionality during integration development.

### 12.7 Implementation phase 6 - Frontend and accessibility

Integrate approved dashboard navigation and role-aware presentation into the existing React and TypeScript frontend.

Validate responsive layouts, keyboard accessibility, focus indicators, mobile interaction, and secure session expiration.

Preserve existing screens and workflows unless changes are explicitly approved.

### 12.8 Implementation phase 7 - Security and regression acceptance

Run existing automated tests before and after each implementation increment.

Add tests for newly introduced authorization, financial, lifecycle, document, and frontend requirements.

Investigate and resolve regressions before proceeding to dependent changes.

Verify database migrations, audit integrity, protected financial information, and distinct-person approvals.

Document test results and remaining exceptions.

### 12.9 Implementation phase 8 - Production readiness

Complete legal, accounting, security, infrastructure, recovery, integration, and operational release gates.

Demonstrate required backup recovery and failover performance rather than relying solely on architecture targets.

Obtain documented business acceptance and authorized production-release approval.

Do not deploy with unresolved mandatory release blockers.

### 12.10 Change history and decision records

Maintain dated records of architecture revisions, approved requirement amendments, implementation decisions, migration plans, test evidence, and acceptance decisions.

Record the responsible authority, affected requirements, reason for change, effective date, and applicable software version.

This Architecture Baseline v2 is a reconciliation and implementation-planning document. It does not supersede an approved requirement solely by restating or interpreting it.

Conflicts and unresolved decisions shall remain explicitly identified until approved through the applicable governance process.
