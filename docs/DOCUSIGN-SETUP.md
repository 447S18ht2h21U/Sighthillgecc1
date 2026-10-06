# GECC Docusign sandbox verification

This slice verifies a sandbox account through confidential OAuth Authorization Code Grant. It does not connect reusable signing credentials or send envelopes. The application is source code awaiting deployment; the callback below is for a backend actually running on your own computer.

## Docusign app settings

In the GECC app's authentication settings, select Authorization Code Grant and configure it as a confidential client that can securely retain a client secret on its backend. Generate the client secret privately. Do not paste the secret, a password, an authorization code, or an access/refresh token into chat or GitHub. No RSA key pair or impersonation scope is needed for this account-verification flow.

For **local development only**, register exactly:

```
http://localhost:8000/api/docusign/callback/
```

This is not an internet-hosted callback. It works only while the GECC backend is running on that computer. A later hosted deployment must use its exact HTTPS URL with the same callback path, and that host must be configured in Django's allowed hosts. Do not register an invented hosted URL.

From the developer account's Apps and Keys page, obtain the **API Account ID** and confirm its Account Base URI is `https://demo.docusign.net`. This ID is distinct from the numeric account number and the integration key/client ID. The flow rejects production base URIs and any different account. The ChatGPT Docusign connector's live account remains separate from this app's sandbox setup.

## Backend configuration

Supply these environment variables on the GECC backend:

```
GECC_DOCUSIGN_CLIENT_ID=<integration key>
GECC_DOCUSIGN_ACCOUNT_ID=<sandbox API account UUID>
GECC_DOCUSIGN_REDIRECT_URI=http://localhost:8000/api/docusign/callback/
GECC_DOCUSIGN_CLIENT_SECRET=<private client secret>
```

Client secret configuration belongs in private server environment/credential storage. `.env` is gitignored, but Django does not automatically load such a file; use your process manager or shell's environment configuration. Never commit it. No token or secret is needed for CI; all authentication tests use synthetic inputs and mock provider responses.

Run local backend and frontend using the main README's instructions. Open the frontend at `http://localhost:5173` so the cookie hostname matches the callback's `localhost`. Using `127.0.0.1` for login and `localhost` for the callback loses the required session binding. Sign in to GECC as the Comptroller, expand **Docusign sandbox setup**, and refresh status. The Verify button remains disabled until configuration passes validation.

Choose **Verify sandbox account**, sign into the developer account, and review Docusign's requested `signature` scope. The callback verifies the account and displays a success message. Return to GECC and refresh status to see the verification evidence. OAuth state expires after ten minutes and is bound to the original GECC session, actor, and configuration. Any provider failure, declined authorization, expired state, session change, or replay requires a fresh verification attempt. Tokens are discarded immediately after account verification; only immutable account identity/verification evidence and an audit event are retained.

## Before hosting or live signing

The verification endpoint is deliberately disabled outside development. Production requires Cognito/MFA, a deployed HTTPS origin, private credential storage with encrypted token retention/refresh and revocation, explicit release permissions, signer-ready document generation, completion/deposit verification, authenticated provider event reconciliation, and signed-document/certificate storage. A past account verification is not a current reusable signing connection. Send for signatures remains disabled.

Django's development server logs redact callback query strings, and callback responses are no-store/no-referrer. Any later reverse proxy, load balancer, monitoring service, or browser analytics must likewise exclude OAuth query strings, bodies, authorization headers, and tokens. The callback catches internal/provider exceptions without exposing their raw contents. Outbox events are audit evidence, not signing commands.

Official references: [confidential Authorization Code Grant](https://developers.docusign.com/platform/auth/confidential-authcode-get-token/), [userinfo](https://developers.docusign.com/platform/auth/reference/user-info/), [base paths](https://developers.docusign.com/platform/api-endpoint-base-paths/), and [integration-key management](https://developers.docusign.com/platform/create-ik-developer-console/).

## Sandbox package and unsent draft test

This development slice supports unsent draft validation only. It **does not implement production signer-ready release**. Approved legal cancellation deadlines, work-completion verification, release approval, sending, authenticated lifecycle reconciliation and signed-document retention remain release blockers.

An assigned Sales Manager or Comptroller can expand a current recipient review and select **Prepare sandbox package**. The immutable package contains separate PDFs generated from the approved templates and snapshot, with the exact reviewed customer/GECC names, GECC role and recorded substitution reason. Printed signer names that do not fit fail rather than silently changing to “See detail”. A routing summary preserves the full names, emails and substitution reason. Original forms carry **SANDBOX TEST - DO NOT SIGN**. Cancellation and completion dates remain blank. Preparation files and prior package files remain downloadable independently.

Only the Comptroller can authorize creation of one unsent draft in the configured sandbox. Select the confirmation checkbox, then **Authorize unsent sandbox draft**. The same confidential OAuth flow verifies the exact sandbox account and uses the token in memory for this single operation; access and refresh tokens are discarded, and no reusable signing connection is established. The callback creates an envelope with fixed `status: created`, the package's exact PDF bytes and coordinate tabs, automatic PDF-field transformation disabled, and the reviewed routing order. No send/update endpoint or embedded sender view is implemented.

GECC commits the draft-attempt intent before the POST and includes its UUID as the provider transaction ID. An ambiguous create or failed inspection is not automatically retried. **NETWORK STARTED**, **CREATED UNVALIDATED** and **RECONCILIATION REQUIRED** need operator inspection in the existing Docusign sandbox Drafts folder; do not prepare another recipient review merely to recreate the same draft. The attempt and any returned envelope ID remain visible. Automated recovery/reconciliation is subsequent work.

After creation, GECC reads the envelope status, recipient/tab definitions and document ID/name list. It requires an unsent draft, the exact signer names/emails/routing, expected tab counts/coordinates/required signatures, and expected document IDs/names. A changed current MSR, newer review, cancellation, altered source or changed GECC account blocks creation or validation. Validation is a point-in-time observation, not a persistent provider connection or approval to send. Provider PDF transformations and visual rendering are not proven by the metadata checks; inspect the actual draft documents and tab appearance manually in Docusign. Editing or sending a draft manually in Docusign is outside these app controls. The 75-day expiration configuration remains tied to a future first send; draft creation does not start installation eligibility or establish a completed-work date.

All external operations are restricted to `https://demo.docusign.net`, bounded JSON replies, certificate-validated HTTPS, denied redirects and fixed UUID paths. Errors omit provider bodies and credentials. Draft creation tests use mocked provider responses; an owner-run sandbox draft and visual review are still required.

Sources: [draft envelope creation](https://www.postman.com/docusign/docusign-s-public-workspace/folder/3y6ue9x/envelopes), [tab placement](https://www.docusign.com/blog/developers/select-the-right-tab-placement-strategy-for-your-docusign-integration), [transaction IDs](https://www.docusign.com/blog/developers/common-api-tasks-use-transactionid-to-find-the-envelope-you-created), and [recipient tab inspection](https://www.docusign.com/blog/developers/dsdev-trenches-tabs-and-custom-fields).
