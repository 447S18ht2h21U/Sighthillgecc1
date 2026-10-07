# Foundation API

All business endpoints require an authenticated session. Mutations also require a valid CSRF token. Local login is available only with `GECC_DEV=1`. Production identity is deliberately unfinished.

| Endpoint | Purpose |
|---|---|
| GET `/api/csrf/` | Obtain CSRF token |
| POST `/api/dev-login/` | Local username/password login |
| GET `/api/me/` | Identity and workflow constants |
| POST `/api/activity/` | Explicit user activity; never called by polling |
| POST `/api/logout/` | End session |
| GET/POST/PATCH `/api/customers/` | Scoped customers; archive rather than delete |
| GET/POST/PATCH `/api/contacts/` | Scoped contacts; one primary per customer |
| GET/POST `/api/projects/` | Scoped projects; POST also creates version 1.0 |
| GET `/api/projects/{id}/history/` | Retained versions |
| POST `/api/projects/{id}/revision/` | `reason`, `expected_approved_id` |
| POST `/api/projects/{id}/state/` | `action`: cancel/reopen, `reason`, `expected_state` |
| GET `/api/projects/{id}/documents/` | All retained project document versions |
| POST `/api/msrs/{id}/documents/` | Prepare `kind`: CONTRACT, INVOICE, COMPLETION_FINANCED, COMPLETION_NON_FINANCED; current approval required |
| GET `/api/documents/` | Scoped document metadata, optional `?msr=` |
| GET `/api/documents/{id}/download/` | Private integrity-checked PDF attachment |
| GET `/api/msrs/{id}/` | Commercial version |
| POST `/api/msrs/{id}/transition/` | `action`: edit/submit/approve/reject, `expected_sequence`, optional `snapshot`/`reason` |
| GET `/api/directory/` | Minimal active sales/reviewer directory |
| GET/POST/PATCH `/api/accounts/` | Comptroller-only local account administration |
| GET `/api/audit/` | Comptroller-only audit history |

Customer/project/account/audit lists use pages of 50. Customer/project lists support scoped `?search=` text lookup. PostgreSQL full-text search and indexed operational filtering are later work. For `edit`, send the complete commercial snapshot; omissions are allowed in a draft but will prevent submission. Snapshot keys are validated and unknown fields rejected. Currency values are decimal strings. Quantities are positive decimal strings. Submission requires explicit equipment/material lists; an empty list records that no items apply.

Stale edits return a validation error with `conflict`; reload before retrying. Duplicate creation warnings return `duplicate_warning`; resubmit with an explicit `duplicate_reason` only after reviewing the match. Document preparation and its audit/outbox record commit atomically. No external delivery, signing, or payment action is executed by the outbox in this slice.


## Signing reviews (local, no external delivery)

- `GET /api/projects/{id}/signing-candidates/?group=COMMERCIAL` returns active role-compatible GECC accounts to assigned Sales Managers/Comptroller. Groups: `COMMERCIAL`, `COMPLETION_FINANCED`, `COMPLETION_NON_FINANCED`.
- `POST /api/msrs/{id}/signing-reviews/` accepts `group`, `customer_name`, `customer_email`, `gecc_signer` (account UUID), `authority_note`, and `substitute_reason` (required for Comptroller certificate substitution). Current approved, active project only; source PDFs must exist. Returns 201 for a new immutable review or 200 for an identical existing review. No signature request is sent.
- `GET /api/projects/{id}/signing-reviews/` returns scoped immutable review history, source hashes, recipient/tab metadata, and computed release checks. Historical reviews survive commercial revisions. Status is `PREPARED`, `REVIEW_REQUIRED`, `SUPERSEDED`, or `CANCELLED`; `provider_status` is null and `send_available` is always false in this slice.

The `envelope_preview` contains no PDF bytes. It is not a complete send payload, and no endpoint exports it to Docusign. Commercial PDFs remain unsigned preparation copies. Explicit release gates must produce signer-ready PDFs and verify work completion/cancellation details before any external invitation.


## Docusign sandbox verification (Comptroller only)

- `GET /api/docusign/status/` returns configuration readiness and historical verification identity only. No secrets or tokens are returned. `send_available` remains false.
- `POST /api/docusign/connect/` starts confidential OAuth Authorization Code Grant with signature scope, returning a short-lived sandbox authorization URL. Requires an authenticated session and CSRF protection. Exact configured account ID, client ID, redirect URI and private client secret are required. Production is disabled.
- `GET /api/docusign/callback/` consumes an actor/session/configuration-bound one-time state, exchanges the authorization code server-side, and verifies the configured sandbox account using userinfo. The callback returns confirmation only and discards access/refresh tokens. Denied/failed authorization requires a fresh connect request. Provider/exception bodies are never included in the response.

Callback path: `/api/docusign/callback/`. Local development URL: `http://localhost:8000/api/docusign/callback/` only with a local backend actually running and a matching login cookie hostname. Hosting, production identity, encrypted reusable credentials, envelope release, provider reconciliation and signed-file retention are future work. See DOCUSIGN-SETUP.md. Reverse-proxy/analytics logs must redact callback queries just as Django's development logs do.

### Development sandbox draft test

- `GET /api/signing-reviews/{id}/sandbox-package/` — scoped package metadata or null; never returns PDF Base64.
- `POST /api/signing-reviews/{id}/sandbox-package/` — assigned manager/Comptroller prepares an immutable test-only package, idempotent for a reviewed plan. Stale/cancelled/changed reviews fail.
- `GET /api/sandbox-packages/{id}/documents/{index}/` — scoped private, checksum-verified historical PDF download.
- `POST /api/sandbox-packages/{id}/connect-draft/` with `{"confirm_unsent_sandbox_draft":true}` — Comptroller, CSRF and actual session required; returns sandbox authorization URL. No token in API output. New OAuth authorization is required, not the historical account proof.
- Existing callback returns `SANDBOX_DRAFT_VALIDATED` and an envelope ID on successful unsent-draft inspection. Failed/ambiguous provider operations require inspection of the recorded attempt and never automatically retry creation.

Packages are marked test-only and do not authorize production release. All send actions remain disabled. Cancellation/completion dates are not fabricated. Provider status, recipient/tab and ID/name inspection remain point-in-time metadata checks; visual review, lifecycle reconciliation and signed retention are subsequent controls.

### Development verification and independent release review

- `GET/POST /api/msrs/{id}/verification-evidence/` — scoped evidence history. The Comptroller records a manual attestation or withdrawal for a current approved active MSR. Evidence references are user-entered provenance, not independently fetched/verified documents.
- Cancellation evidence requires `kind: CANCELLATION_DEADLINE`, boolean `verified`, `source_reference`, `verification_note`, an exact timezone-aware `deadline`, and `notice_and_applicability_checked: true` when verified. The app does not calculate a legal deadline.
- Completion evidence requires `kind: WORK_COMPLETION`, boolean `verified`, provenance/note, an ISO `completion_date` no later than today in Eastern time, `work_verified`, `permits_inspections_checked`, `exceptions_resolved` all true, and a recorded Installation Manager unavailability/substitution reason. Only Comptroller manual capture as substitute is supported here; assigned Installation Manager operational access is pending.
- `GET/POST /api/signing-reviews/{id}/release-packages/` — current reviewed recipients, exact approved snapshot/template, and latest applicable evidence produce an immutable unsigned release-review package. No PDF Base64 in API metadata.
- `GET /api/release-packages/{id}/documents/{index}/` — scoped, checksum-verified historical release-review PDF.
- `POST /api/release-packages/{id}/decisions/` — `decision: APPROVED|REVOKED`, note, and explicit `documents_and_evidence_reviewed: true` for approval. A different active assigned manager/Comptroller from both evidence recorder and package preparer must approve. Revocation is an additional immutable decision.

Evidence corrections/withdrawals, recipient changes, revisions, cancellation, reviewer deactivation or loss of reviewer authority dynamically block prior approvals. Decisions and evidence retain complete immutable history with audit/outbox atomicity and database guards. Release approval is internal development review only: it never creates/sends a provider envelope, proves completion/payment, or enables installation. Production authentication, sending, authenticated signature/deposit/lifecycle reconciliation and signed retention remain pending. Existing sandbox drafts retain their test markings and are not converted or resent.


### Read-only sandbox reconciliation (development only)

`POST /api/sandbox-packages/{id}/connect-check/` requires an authenticated Comptroller session, CSRF and `{"confirm_read_only_check":true}`. It starts fresh sandbox OAuth, bound to the saved account, package digest and known envelope ID. Unknown envelope IDs and in-flight creates cannot be reconciled or adopted by this endpoint. New authorization supersedes older checks. The callback reads envelope status twice around recipient/tab and document-list reads; it never creates, updates, sends or voids an envelope.

Package GET includes immutable `attempt.observations`, newest authorization first. Outcomes: `MATCHED`, `CHANGED`, `BLOCKED`, `READ_FAILED`, `SUPERSEDED`. Authorization pending changes the attempt to `RECHECK_PENDING`; successful current metadata checks restore `DRAFT_VALIDATED`, while discrepancies, local supersession and failures require reconciliation. Failed/expired OAuth leaves a pending check that can be restarted. Creation evidence remains unchanged. Each recorded observation and audit/outbox entry commit atomically.

This is a point-in-time metadata comparison, not an atomic provider snapshot or provider PDF byte comparison. Visual document review remains required. Historical/superseded envelopes can be read but cannot regain local eligibility. `send_available` remains false, including when the provider reports sent or completed. No tokens or provider error bodies are retained. Polling, webhooks, unknown-ID lookup and signed-document retention remain pending.


### Fictional sandbox signing tests and retained artifacts

`GET/POST /api/release-packages/{id}/signing-tests/` prepares a separate test package from a current independently approved release package. POST is Comptroller-only and requires `customer_email`, `gecc_email`, `test_note`, `fictional_project_confirmed:true`, and `emails_controlled:true`. Source verification must identify a simulated/synthetic reference. Both distinct recipient emails must belong to `GECC_SANDBOX_TEST_EMAILS` on the backend. Emails are overridden only for this explicitly approved test; original MSRs, source reviews and DO NOT SIGN drafts are never converted.

`POST /api/signing-tests/{id}/decisions/` accepts APPROVED/REVOKED, note, and `exact_test_reviewed:true` for approval. Another authorized reviewer must approve the exact new PDF hashes, names, controlled emails and routing. Changes to source approval, verification, signer eligibility or the email allowlist block sending. The test documents have a visible SANDBOX SIGNING TEST banner on every page and make no actual agreement/completion/payment/lender assertion.

`POST /api/signing-tests/{id}/connect/` accepts `{"operation":"SEND"|"READ","confirmed":true}`. Authenticated Comptroller session, CSRF and fresh sandbox OAuth are required. SEND additionally requires `GECC_SANDBOX_SIGNING_SEND_ENABLED=1`; sending defaults to disabled. Authorization pins the account, current test approval, email policy and package digest. A one-time send intent commits before the fixed sandbox POST. Unsigned requests expire after 75 days. Neither a timeout nor a failed inspection permits another send. Another pending/uncertain send for the same project workflow also blocks replacement sends. Unknown envelope-ID recovery remains manual and is not implemented. No production API origin or arbitrary provider resource is accepted.

READ checks the known envelope's status, recipients, routing, tab positions and document list, with envelope status reads before/after. Completed status requires both recipients' completed status and timezone-aware signing timestamps no later than the envelope's completion time. Original signed document PDFs and the Docusign completion certificate are retained together, atomically with immutable observation/audit/outbox history and SHA-256 digests. Partial retrieval, malformed PDFs, changed metadata, newer authorization or audit failure stores no partial bundle. Each PDF is limited to 8 MiB/150 pages, total bundle 24 MiB. Existing retained bundles are checked locally and never overwritten; later reads do not re-download the original completion certificate. Known sent historical/revoked/cancelled project tests remain readable for retention, without restoring project eligibility.

`GET /api/signing-tests/{id}/documents/{index}/` downloads the reviewed test PDFs. `GET /api/signing-test-documents/{id}/` downloads checksum-verified retained PDFs. All endpoints use project access scope and private/no-store responses. Access/refresh tokens and provider error bodies are never retained.

These are fictional tests with manual attestation, not legal signature validation or confirmation of actual work. Reads are point-in-time observations, not atomic provider snapshots. No webhooks, scheduled polling, automatic project completion, deposit verification, production identity, production sending or disaster-recovery guarantee is implemented.

### Account management

`GET /api/accounts/` and `GET /api/accounts/{id}/` are active-Comptroller-only and return safe profile fields plus `revision`, with private/no-store responses. Lists use 50-record pagination. POST requires a local password, valid email/role/uppercase initials and `change_note`. PATCH requires the current `expected_revision` and `change_note`; include `password` only for an intentional reset. The server locks actor/target accounts, rechecks current authorization and rejects stale updates. Self-role changes and self-deactivation are prohibited. No delete endpoint is offered; deactivation preserves all linked records. Audits include safe before/after values, note and a password-changed boolean, never credentials. Production writes remain blocked pending the identity adapter. No email is sent by account provisioning.

### Customer and contact management

Customer/contact reads and mutations remain role- and record-scoped and use private/no-store responses. Both resources expose a `revision`; PATCH requires `expected_revision` and `change_note`. The API locks the current actor and parent/customer/target rows before validating edits. Approved MSRs and documents are never rewritten by master-record corrections. Customer archiving blocks new projects and contacts while preserving history. Duplicate name/address identity edits require `duplicate_reason`; ordinary updates to an already-reviewed duplicate do not repeatedly require an override.

`GET /api/contacts/?customer={uuid}&page={n}` filters contacts within authorized customer scope. POST requires `customer`, `name` and `change_note`; optional fields are `relationship`, `email`, `phone`, `primary`. Setting primary true requires `expected_primary_id` equal to the current primary ID (empty string when none). Replacing another primary additionally requires `replace_primary_confirmed:true`. Previous contact demotion, target create/update and audits are atomic. Contacts cannot move customer or be deleted through these endpoints. No email is sent.


### Scoped customer/project search

`GET /api/customers/?search={term}&status=ACTIVE|ARCHIVED&page={n}` searches master name/address/email/phone and related contact name/email/phone. Omit status for all customers. Contact joins are deduplicated before counting/pagination. `GET /api/projects/?search={term}&state=DRAFT|SUBMITTED|APPROVED|REJECTED|REVISED|CANCELLED&sort=NEWEST|OLDEST|CODE&page={n}` searches project code/location, customer master name and names in the current approved/pending MSR. Omit state for all states; default sort is newest. Sorts include UUID tie-breaks; page size is 50. The same current-role/record scopes apply before matching, and current inactive actors receive no records.

Terms are trimmed, case-insensitive literal substrings and may be at most 200 characters. Invalid nonblank filters or excessive terms return 400. Empty filters mean all/default. Filters apply only to lists; detail and workflow endpoints retain their original scope. Responses are private/no-store. Searches do not write business/audit events. This is database field search, not full-text PDF search, fuzzy matching or phone normalization.
