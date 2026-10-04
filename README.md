# GECC foundation application

The first development slice implements customer/contact records, assigned projects, draft Master Sales Records (MSRs), review decisions, immutable approvals, revisions, cancellation/reopening, account permissions, and a transactional audit/outbox foundation.

The approved architecture is in [docs/GECC-Implementation-Architecture-v1.2.html](docs/GECC-Implementation-Architecture-v1.2.html). The original baseline documents remain in this repository. Where those older documents conflict with the later approved architecture, the approved five-calendar-day installation rule and retained 50% deposit option take precedence.

## Run locally

Requires Python 3.12 and Node 22 or newer. Run both commands below from the repository root in separate terminals. All credentials below are supplied by the developer; none are built into the application.

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

The GitHub workflow uses PostgreSQL 17 to exercise database triggers, concurrent writes, and sequence rollback behavior. The local SQLite run skips the three PostgreSQL-specific tests. Database immutability is enforced by migration-installed triggers, including writes that bypass Django's model methods. Database operators capable of altering triggers remain privileged; independent audit anchoring and backup access separation are still pending.

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

Document generation from the approved interactive PDF templates, Docusign envelopes and role enforcement, Google Drive/Gmail/S3 adapters, installation scheduling and deposit verification, financial calculations/ledger, reports, outbox delivery workers, AWS infrastructure, external audit anchors, and recovery drills are subsequent slices. The application cannot yet mark a project Completed or send signature invitations. Installation Managers' operational views and cancellation requests follow in the installation slice.

The daily backup/retention requirements and RPO/RTO targets are design requirements, not claims established by this foundation build. No AWS resources are provisioned here.
