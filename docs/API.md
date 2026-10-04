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
| GET `/api/msrs/{id}/` | Commercial version |
| POST `/api/msrs/{id}/transition/` | `action`: edit/submit/approve/reject, `expected_sequence`, optional `snapshot`/`reason` |
| GET `/api/directory/` | Minimal active sales/reviewer directory |
| GET/POST/PATCH `/api/accounts/` | Comptroller-only local account administration |
| GET `/api/audit/` | Comptroller-only audit history |

Customer/project/account/audit lists use pages of 50. Customer/project lists support scoped `?search=` text lookup. PostgreSQL full-text search and indexed operational filtering are later work. For `edit`, send the complete commercial snapshot; omissions are allowed in a draft but will prevent submission. Snapshot keys are validated and unknown fields rejected. Currency values are decimal strings. Quantities are positive decimal strings. Submission requires explicit equipment/material lists; an empty list records that no items apply.

Stale edits return a validation error with `conflict`; reload before retrying. Duplicate creation warnings return `duplicate_warning`; resubmit with an explicit `duplicate_reason` only after reviewing the match. No document, payment, or external delivery action is executed by the outbox in this slice.
