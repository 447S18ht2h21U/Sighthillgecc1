# GECC foundation application

The foundation and document preparation slices implement customer/contact records, assigned projects, draft Master Sales Records (MSRs), review decisions, immutable approvals, revisions, cancellation/reopening, account permissions, a transactional audit/outbox foundation, and interactive PDF preparation from approved versions.

The approved architecture is in [docs/GECC-Implementation-Architecture-v1.2.html](docs/GECC-Implementation-Architecture-v1.2.html). The original baseline documents remain in this repository. Where those older documents conflict with the later approved architecture, the approved five-calendar-day installation rule and retained 50% deposit option take precedence.

## Run locally

Requires Python 3.12 and Node 22 or newer. The owner-approved PDF files are supplied privately and are not committed to this public repository. Set `GECC_PDF_TEMPLATE_DIR` to their private directory, or place them locally in the ignored `backend/core/pdf_templates/` directory. The template manifest pins their approved hashes. Run both commands below from the repository root in separate terminals. All credentials below are supplied by the developer; none are built into the application.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.lock.txt
export GECC_DEV=1
export GECC_DEMO_PASSWORD='choose-a-12-plus-character-password-with-a-number-and-special-character'
python backend/manage.py migrate
python backend/manage.py bootstrap_dev
python backend/manage.py runserver 127.0.0.1:8000
```

```bash
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. Local demo usernames are `sales`, `manager`, and `comptroller`, with your supplied password. Create a customer, create a project assigned to `sales` and reviewed by `manager`, save/submit the MSR, then sign in as `manager` to approve or reject it. Start a revision to see the approved version retained separately from the pending draft. A user who created or last prepared a version cannot approve it; a different authorized reviewer is required.

SQLite is a convenience for local exploration only. It does not establish production concurrency or non-reuse of project sequence numbers after transaction rollback.

### Use PostgreSQL locally

```bash
export PGPASSWORD='choose-a-local-database-password'
docker compose up -d
export GECC_DEV=1 PGHOST=127.0.0.1 PGPORT=5432 PGDATABASE=gecc PGUSER=gecc
python backend/manage.py migrate
python backend/manage.py bootstrap_dev
python backend/manage.py runserver 127.0.0.1:8000
```

## Validate

```bash
GECC_DEV=1 python backend/manage.py check
GECC_DEV=1 python backend/manage.py makemigrations --check --dry-run
GECC_DEV=1 python backend/manage.py test core
GECC_DEV=1 python backend/manage.py verify_audit
cd frontend && npm run build
```

The GitHub workflow uses PostgreSQL 17 to exercise database triggers, concurrent writes, and sequence rollback behavior. The local SQLite run skips the four PostgreSQL-specific tests. Database immutability is enforced by migration-installed triggers, including writes that bypass Django's model methods. Database operators capable of altering triggers remain privileged; independent audit anchoring and backup access separation are still pending.

## Implemented behavior

- Seven business roles; only the Comptroller manages business accounts. Sales Associates see their assigned projects, Sales Managers see projects assigned to them for review, and the Comptroller sees all commercial records. Other roles receive no commercial access in this slice.
- UUID identifiers, Eastern business dates, UTC-aware timestamps, and USD validated to two decimal places. Project sequence starts at 101; PostgreSQL reservations survive transaction rollback.
- Explicit duplicate warnings with recorded override reasons. No hard-delete API for customers, contacts, projects, versions, or accounts.
- Draft/rejected versions can be edited. Submission validates required commercial fields and pricing arithmetic, then freezes the snapshot. Approval freezes every version field.
- Revision reasons, sequential version numbers, a distinct current-approved pointer, and exact retained snapshots for review decisions. Customer master edits do not change approved commercial snapshots.
- Project locks and expected edit sequence numbers reject stale updates. Audit events and outbox entries commit atomically with business changes. The append-only audit chain can be verified with `verify_audit`.
- CSRF-protected local login and mutation endpoints, a 12-character password policy, and a server-side 30-minute idle timeout. Reads and dashboard refreshes do not extend the session.
- Both payment options remain available: 50% deposit / 50% at completion, or 100% at completion. Deposit legality and project-specific cancellation deadlines still require the previously identified legal validation.
- The installation eligibility helper adds five Eastern calendar days after the later customer contract/invoice signature and respects a later applicable cancellation deadline. It does not treat five days as a fixed 120 hours across daylight-saving changes. Missing signatures or cancellation deadlines keep the gate unset.
- Explicit GECC/customer signature field identifiers and signing order for contract, invoice, financed certificate, and non-financed certificate are represented in the workflow rules.

## Remaining work before production

This is development software, not a deployed production service. Production login is intentionally unavailable until the Cognito identity adapter and SMS MFA are implemented. Local credentials are never a substitute for that adapter.

Docusign account connection, signer-ready document release, provider status reconciliation, Google Drive/Gmail/S3 adapters, installation scheduling and deposit verification, financial calculations/ledger, reports, outbox delivery workers, AWS infrastructure, external audit anchors, and recovery drills are subsequent slices. The application cannot yet mark a project Completed or send signature invitations. Completion certificates are unsigned preparation copies, with completion and signature dates unset. Installation Managers' operational views and cancellation requests follow in the installation slice.

The daily backup/retention requirements and RPO/RTO targets are design requirements, not claims established by this foundation build. No AWS resources are provisioned here.


## Prepare documents and review screens

After privately configuring the approved templates, an assigned Sales Manager or the Comptroller can use the Documents section to prepare a contract, invoice, or matching financed/non-financed completion certificate. Financing, contact details, and installation city/state/ZIP are commercial snapshot fields. Older approved versions that lack a financing selection require a newly approved revision before contract/certificate preparation; they are never silently updated.

The original form pages, company logo, Maryland artwork, and native customer/GECC signature widgets remain. Generated files add full approved project detail pages so scope, equipment, materials, prices, and terms cannot be lost to fixed field sizes. Commercial fields are populated and locked; signer/date fields remain interactive. Every original form page carries an unsigned-preparation watermark. Five-calendar-day wording and both payment options remain in the templates and project detail.

Generated PDFs are immutable, linked to the precise MSR, and retain template, snapshot, and file SHA-256 digests. Repeated generation for the same template/renderer/version returns the existing document. Old-version files remain downloadable after a revision is approved. Downloads are scoped, private, and checksum-verified. For this development slice, prepared bytes are stored atomically in the database; protected Drive/S3 storage and signing adapters will replace that preparation store before production.

Synthetic fixtures can be generated with `python backend/tools/create_test_templates.py --output /tmp/gecc-test-templates`. Tests can explicitly set `GECC_PDF_TEMPLATE_DIR=/tmp/gecc-test-templates` and `GECC_SYNTHETIC_TEMPLATES=1` in development only. The production hash check never accepts this development override. The original templates were separately exercised and visually reviewed locally.

The renderer currently supports Western European text with the templates' standard fonts; unsupported characters fail preparation rather than being silently lost. Full multilingual font shaping is a later adapter.

The browser test creates an isolated synthetic development database, exercises sign-in, customer/project creation, submission, approval, revisions, all four PDF downloads, preservation of older document versions, and the mobile layout:

```bash
cd frontend
npx playwright install --with-deps chromium
npm run test:screen
```

CI creates synthetic templates with matching fields, runs this screen review, and saves synthetic screenshots/PDFs as a workflow artifact, alongside the PostgreSQL API checks and frontend build. No production records or credentials are used.


## Signing recipient review

After preparing the PDFs, the assigned Sales Manager or Comptroller can save a recipient review in the Signing review section. A commercial review bundles the contract and invoice into one routing plan: the customer signs both documents in routing order 1, and GECC signs both in routing order 2. GECC may be the assigned Sales Manager or an active Comptroller. Financed and non-financed certificate reviews match the approved financing selection and route to the Installation Manager first, then the customer. A Comptroller substitution requires a recorded Installation Manager unavailability reason.

Customer signer name, email, and the preparer's identity/authority review are captured explicitly. GECC identity comes from an active role-compatible account with a full name and email. Reviews pin immutable source document IDs, hashes, and the approved MSR. Duplicate reviews return the existing record; changed recipients create a new record. New reviews or approved MSRs supersede earlier reviews, and cancellation or changed signer accounts block release. Database guards prevent editing or deleting review evidence, which is committed atomically with the audit/outbox event.

This slice creates **local metadata previews**, not Docusign envelopes. The previews map separate signature, printed-name, signed-date, and invoice payment-initial widgets to each recipient using explicit document/page coordinates. Automatic PDF field transformation is disabled because it assigns transformed fields to one recipient. The preview requests draft status and 75-day unsigned-request expiration; the actual initial-send time is not fabricated. Preparation PDF bytes are deliberately absent. No external API call, invitation, completed signature, installation eligibility, or provider status is asserted by this feature.

Before live signing: connect the Docusign account using OAuth, implement immutable signer-ready PDFs (including verified project-specific cancellation and completion data), verify tab rendering in a sandbox draft, build explicit release/send authorization, and implement authenticated/idempotent provider status reconciliation and signed document/certificate retention. Signer-ready PDFs must populate the actual reviewed signer name instead of the commercial customer name currently printed on preparation copies. A completed-work record and operational access for the Installation Manager are also required before releasing a completion certificate. The disabled Send for signatures button lists these release blockers.

API semantics were checked against Docusign's [envelopes reference](https://developers.docusign.com/docs/esign-rest-api/reference/envelopes/envelopes/), [PDF transformation rules](https://developers.docusign.com/docs/esign-rest-api/esign101/concepts/tabs/pdf-transform/), [tab placement](https://www.docusign.com/blog/developers/select-the-right-tab-placement-strategy-for-your-docusign-integration), and [expiration guidance](https://www.docusign.com/blog/developers/dsdev-trenches-reminders-expirations). The metadata is a preview and must pass sandbox validation before use.


## Docusign sandbox account verification

The Comptroller can expand Docusign sandbox setup to review backend configuration and start confidential OAuth account verification. The exact sandbox account is checked against Docusign userinfo, and immutable verification evidence is committed with the audit event. Access and refresh tokens are discarded; this is not a reusable signing connection. Production access and sending remain disabled. Session-bound, ten-minute authorization state is consumed before provider calls, so failures and replays require a fresh flow. Callback query strings are redacted from Django development logs.

See [Docusign setup](docs/DOCUSIGN-SETUP.md) for private environment configuration, the exact local callback, and hosting requirements. The application has not been deployed. Local callbacks are usable only with the backend running on that computer, and a hosted deployment will need its own verified HTTPS callback URL.

## Unsent Docusign sandbox draft testing

A current recipient review can now generate an immutable **sandbox package** with reviewed signer names, GECC role, substitution reason and separate test-only PDFs. An authorized Comptroller can start a fresh OAuth flow to create one unsent developer-sandbox draft and inspect its recipient routing, tab coordinates and document ID/name list. No tokens are retained, sending remains disabled, and a timed-out or failed draft attempt requires inspection instead of automatic recreation. This is not production signer-ready release: cancellation/work-completion verification and release authorization are still pending. See [Docusign setup](docs/DOCUSIGN-SETUP.md) for the full test flow and limits.

## Manual verification and separate release review

The Comptroller can expand **Project verification evidence** for an approved MSR to record a manually reviewed cancellation deadline or completed-work verification with provenance, checks and a substitution reason. Evidence corrections and withdrawals append immutable records. The application does not independently inspect referenced evidence or determine the legally applicable deadline.

An assigned manager or Comptroller can prepare separate unsigned release-review PDFs from a current signing review and current applicable evidence. These PDFs preserve exact reviewed signer names, populate the manually verified contract deadline or certificate completion date, and append full routing/provenance detail. Prior preparation/sandbox PDFs are retained unchanged. Another authorized person must review the exact package and evidence and record a release decision; neither the package preparer nor evidence recorder can approve their own work. Prepare packages as Comptroller and review as the assigned manager in a two-account local test.

Evidence withdrawal/correction, recipient changes, a new approved MSR, cancellation, and reviewer authority changes invalidate prior approval. Sending remains disabled after APPROVED: production identity, send authorization, authenticated provider lifecycle/signature and deposit verification, Installation Manager operational assignment/views and signed retention are not complete. Recorded verification is a manual attestation, not automated proof. Only Comptroller manual completion capture as an authorized substitute is implemented in this slice.


Read-only sandbox draft checks are available to the Comptroller under **Sandbox draft test**. Select **I authorize a read-only check of this existing sandbox draft**, then **Check existing sandbox draft** and complete fresh sandbox authorization. Return to GECC and **Refresh sandbox draft status**. Observation history preserves successful checks, discrepancies and read failures. This checks known envelope metadata only; PDF appearance still requires visual review, and sending remains disabled. Superseded project packages remain blocked even when provider metadata matches. A pending authorization can be restarted; an ambiguous create with no saved envelope ID cannot create a replacement.


Fictional sandbox signing tests now have a separate **Sandbox signing test** section beneath each approved release package. The Comptroller prepares separate signing-test PDFs with two controlled email addresses, and another reviewer approves the exact package. To configure local tests, privately set `GECC_SANDBOX_TEST_EMAILS` to the two distinct controlled addresses on the backend. Leave `GECC_SANDBOX_SIGNING_SEND_ENABLED` unset until the user is ready to authorize actual sandbox invitations; only the value `1` enables that action. Fresh OAuth is required for every send/status read and no tokens are stored.

The provider send is attempted once. Pending/uncertain sends block additional packages for the same project workflow. Once both recipients complete signing, a read-only check can retain all signed PDFs plus Docusign's completion certificate, with immutable digests and history. Existing DO NOT SIGN drafts remain test history; they are never converted into signing envelopes. Production signing, work/permit/financial verification, polling/webhooks and disaster recovery remain pending.

## Comptroller user management

The Comptroller can open **User management** to list all accounts with pagination, create local users, edit names/email/initials and roles, activate/deactivate accounts, and optionally reset another user's local password. Each change requires a note. The account API returns a revision value; PATCH must submit the current `expected_revision` to reject stale edits under database locks. Creation and edits commit safe before/after metadata and audit history together; passwords and credential hashes are never returned or audited. Role and active-status changes to your own account remain blocked. Existing business history is retained. Production identity provisioning still requires the Cognito adapter; this screen manages local development accounts only.

The owner verified all three sandbox signing workflows and seven retained files on October 6, 2026. On October 7 the owner verified a local/external backup and opened every retained file from an isolated restore copy, then returned to the original database with sandbox sending disabled. This is a local recovery test, not evidence of production zero-data-loss or 15-minute recovery capability.

**Deferred until after MVP:** simplify opening and reviewing multiple documents, as requested by the owner on October 7, 2026.

## Customer editing and contacts

Authorized Sales Associates, assigned Sales Managers and the Comptroller can open **Manage customers** to edit scoped customer details and add/edit contacts. Lists are paginated. Updates require a change note and the current record revision, validated under locks. Customer corrections do not modify any existing MSR snapshot or generated document. Archiving preserves history and blocks new projects/contact additions; restoring is an audited update. Identity changes that match another customer require an explicit duplicate override reason.

Each customer has at most one primary contact. Replacing it requires confirmation and the current primary contact ID; the former contact remains, and demotion/promotion plus audit events commit together. Contact records cannot move between customers or be deleted through the API. Production authentication/hosting and remaining MVP screens are still pending.

On October 7, 2026, the owner verified account creation, assigned-record isolation, deactivation/login blocking, reactivation, role change, password reset and protected self-role/active controls in the local User management screen.
