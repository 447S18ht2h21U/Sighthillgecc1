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
