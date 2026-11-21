import { useEffect, useState } from 'react';

type API = <T>(
  path: string,
  method?: string,
  data?: unknown
) => Promise<T>;

type Status = {
  project_id: string;
  authorization_state: string;
  preparation_ready: boolean;
  preparation_state: string;
  source_stage?: string;
  intent_id: string | null;
  provider_draft_created: boolean;
  provider_request_authorized: boolean;
  send_authorized: boolean;
  provider_signature_verified: boolean;
  project_completion_authorized: boolean;
};

type UnsignedPdfCheck = {
  project_id: string;
  status: string;
  unsigned_pdf_sha256: string;
  required_inspection_findings: number;
  required_signature_fields: number;
  read_only: boolean;
  document_saved: boolean;
  provider_envelope_created: boolean;
  document_sent: boolean;
  provider_signature_verified: boolean;
  receipt_issuance_authorized: boolean;
  project_completion_authorized: boolean;
};

const messages: Record<string, string> = {
  NOT_AUTHORIZED: 'No inspection draft authorization recorded.',
  DRAFT_INTENT_RECORDED: 'Inspection draft intent recorded. No DocuSign envelope has been created or sent.',
  PROJECT_CANCELLED: 'Project cancelled. Authorization unavailable.',
  APPROVED_MSR_REQUIRED: 'A current approved Master Sales Record is required.',
  AUTHORIZATION_CONFLICT: 'Conflicting authorization records require review.',
  AUTHORIZATION_INVALID: 'Authorization evidence failed validation.',
  AUTHORIZER_INELIGIBLE: 'The original authorizer is no longer eligible.',
};

export function InspectionDraftWorkflow5189({
  api,
  projectId,
  actorRole,
}: {
  api: API;
  projectId: string;
  actorRole: string;
}) {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [revision, setRevision] = useState(0);
  const [pdfCheck, setPdfCheck] = useState<UnsignedPdfCheck | null>(null);
  const [pdfError, setPdfError] = useState('');
  const [pdfBusy, setPdfBusy] = useState(false);

  const canAuthorize =
    actorRole === 'CEO' || actorRole === 'SALES_MANAGER';

  const canView =
    canAuthorize || actorRole === 'COMPTROLLER';

  useEffect(() => {
    let cancelled = false;

    setStatus(null);
    setError('');
    setConfirmed(false);
    setPdfCheck(null);
    setPdfError('');

    if (!canView || !projectId) {
      return () => { cancelled = true; };
    }

    void api<Status>(
      `inspection-draft-intents/${encodeURIComponent(projectId)}/status/`
    ).then(result => {
      if (!cancelled) {
        if (
          result.project_id !== projectId ||
          !Object.prototype.hasOwnProperty.call(
            messages, result.authorization_state
          ) ||
          typeof result.preparation_ready !== 'boolean' ||
          ![
            'SOURCE_NOT_VERIFIED',
            'SOURCE_VERIFIED_PREPARATION_PENDING',
            'PREPARATION_VERIFIED'
          ].includes(result.source_stage ?? '') ||
          (result.preparation_ready === true &&
           result.source_stage !== 'PREPARATION_VERIFIED') ||
          result.provider_draft_created !== false ||
          result.provider_request_authorized !== false ||
          result.send_authorized !== false ||
          result.provider_signature_verified !== false ||
          result.project_completion_authorized !== false
        ) {
          setError('Inspection signing readiness failed safety verification.');
          return;
        }
        setStatus(result);
      }
    }).catch((reason: unknown) => {
      if (!cancelled) {
        setError(
          reason instanceof Error ? reason.message : 'Unable to load inspection status.'
        );
      }
    });

    return () => { cancelled = true; };
  }, [api, projectId, canView, revision]);

  if (!canView || !projectId) return null;

  async function authorize() {
    if (
      !canAuthorize ||
      !confirmed ||
      busy ||
      !status ||
      status.authorization_state !== 'NOT_AUTHORIZED' ||
      status.preparation_ready !== true
    ) return;

    setBusy(true);
    setError('');

    try {
      const result = await api<{
        status: string;
        provider_request_authorized: boolean;
        send_authorized: boolean;
      }>(
        `inspection-draft-intents/${encodeURIComponent(projectId)}/authorize/`,
        'POST',
        { confirm_inspection_draft_intent: true }
      );

      if (
        result.status !== 'DRAFT_INTENT_RECORDED' ||
        result.provider_request_authorized !== false ||
        result.send_authorized !== false
      ) {
        throw new Error('Unexpected inspection authorization response.');
      }

      setConfirmed(false);
      setRevision(value => value + 1);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : 'Inspection authorization was not completed.'
      );
    } finally {
      setBusy(false);
    }
  }

  async function verifyUnsignedPdf() {
    if (
      !canAuthorize ||
      busy ||
      pdfBusy ||
      !status ||
      status.preparation_ready !== true ||
      status.source_stage !== 'PREPARATION_VERIFIED' ||
      !['NOT_AUTHORIZED', 'DRAFT_INTENT_RECORDED'].includes(
        status.authorization_state
      ) ||
      status.provider_draft_created !== false ||
      status.provider_request_authorized !== false ||
      status.send_authorized !== false ||
      status.provider_signature_verified !== false ||
      status.project_completion_authorized !== false
    ) return;

    setPdfBusy(true);
    setPdfCheck(null);
    setPdfError('');

    try {
      const result = await api<UnsignedPdfCheck>(
        `inspection-draft-intents/${encodeURIComponent(projectId)}/unsigned-pdf-preflight/`
      );

      if (
        result.project_id !== projectId ||
        result.status !== 'UNSIGNED_PDF_VERIFIED_OFFLINE' ||
        !/^[0-9a-f]{64}$/.test(result.unsigned_pdf_sha256) ||
        result.required_inspection_findings !== 5 ||
        result.required_signature_fields !== 2 ||
        result.read_only !== true ||
        result.document_saved !== false ||
        result.provider_envelope_created !== false ||
        result.document_sent !== false ||
        result.provider_signature_verified !== false ||
        result.receipt_issuance_authorized !== false ||
        result.project_completion_authorized !== false
      ) {
        throw new Error(
          'Unsigned inspection document failed safety verification.'
        );
      }

      setPdfCheck(result);
    } catch (reason) {
      setPdfError(
        reason instanceof Error
          ? reason.message
          : 'Unable to verify unsigned inspection document.'
      );
    } finally {
      setPdfBusy(false);
    }
  }

  const unauthorizedProviderState =
    status?.provider_draft_created === true ||
    status?.provider_request_authorized === true ||
    status?.send_authorized === true ||
    status?.provider_signature_verified === true ||
    status?.project_completion_authorized === true;

  return (
    <section className="veridian-guide-banner veridian-guide-banner--info">
      <h4>Installation inspection signing</h4>

      <p>
        Development-only inspection draft preparation and authorization.
        The Installation Manager must complete their own inspection findings
        and signature through DocuSign in the later signing phase.
      </p>

      {status && (
        <p role="status">
          <strong>Authorization status: </strong>
          {messages[status.authorization_state] ?? status.authorization_state}
        </p>
      )}

      {status && (
        <p role="status">
          <strong>Inspection source readiness: </strong>
          {status.preparation_ready
            ? 'Independently verified for offline draft preparation.'
            : status.source_stage === 'SOURCE_VERIFIED_PREPARATION_PENDING'
              ? 'Installation source evidence is verified. An authorized CEO or Sales Manager must complete the independent attestation preparation before draft authorization is available.'
              : 'Not yet verified. The Installation Manager must complete the installation inspection and retain the supporting source PDF. The evidence must pass independent checks before draft authorization.'}
        </p>
      )}

      {status && !unauthorizedProviderState && (
        <div aria-label="Inspection signing preparation steps">
          <h4>Inspection signing preparation steps</h4>
          <p>
            <strong>1. Installation inspection evidence: </strong>
            {status.source_stage === 'SOURCE_NOT_VERIFIED'
              ? 'Verified installation inspection source evidence is still required.'
              : 'Installation source evidence passed its internal integrity checks. DocuSign signing is not yet verified.'}
          </p>
          <p>
            <strong>2. Draft preparation: </strong>
            {status.preparation_ready
              ? 'Verified for preparing an unsigned inspection draft.'
              : status.source_stage === 'SOURCE_VERIFIED_PREPARATION_PENDING'
                ? 'CEO or Sales Manager preparation checks are still required.'
                : 'Not ready. Inspection evidence must be completed first.'}
          </p>
          <p>
            <strong>3. Draft authorization: </strong>
            {status.authorization_state === 'DRAFT_INTENT_RECORDED'
              ? 'An internal authorization record exists. No DocuSign document was sent.'
              : status.authorization_state === 'NOT_AUTHORIZED'
                ? 'Not recorded.'
                : 'Unavailable or requires review.'}
          </p>
          <p>
            <strong>4. DocuSign signature and date: </strong>
            Not verified. The Installation Manager must personally
            complete signing through the approved DocuSign process.
          </p>
          <p className="muted">
            Only the CEO or Sales Manager can authorize preparation
            or sending. This screen does not authorize sending.
            The FINAL Receipt and project completion require separate
            verified evidence and approvals.
          </p>
        </div>
      )}

      {canAuthorize && (
        <div aria-label="Unsigned inspection PDF verification">
          <h4>Unsigned inspection PDF verification</h4>
          <p className="muted">
            Check the unsigned inspection document against the approved
            Master Sales Record, inspection evidence, and required
            signing fields. This does not download, save, or send a PDF.
          </p>
          <button
            type="button"
            className="quiet"
            disabled={
              busy ||
              pdfBusy ||
              !status ||
              status.preparation_ready !== true ||
              status.source_stage !== 'PREPARATION_VERIFIED' ||
              !['NOT_AUTHORIZED', 'DRAFT_INTENT_RECORDED'].includes(
                status.authorization_state
              ) ||
              unauthorizedProviderState
            }
            onClick={() => { void verifyUnsignedPdf(); }}
          >
            {pdfBusy
              ? 'Checking unsigned inspection PDF...'
              : 'Verify unsigned inspection PDF'}
          </button>
          {status && status.preparation_ready !== true && (
            <p className="muted">
              Verification is unavailable until the installation
              inspection source and independent preparation checks
              have been completed.
            </p>
          )}
          {pdfError && <p role="alert">{pdfError}</p>}
          {pdfCheck && (
            <div role="status">
              <p>
                <strong>Unsigned inspection PDF: </strong>
                Verified for offline preparation only.
              </p>
              <p className="muted">
                Five inspection findings and two DocuSign signing
                fields checked. No PDF saved or sent. No signature
                or project completion verified.
              </p>
            </div>
          )}
        </div>
      )}

      {unauthorizedProviderState && (
        <p role="alert">
          Inspection evidence reports unexpected provider or completion
          authority. Do not proceed.
        </p>
      )}

      {!status && !error && <p>Loading inspection authorization status...</p>}

      {canAuthorize &&
        status?.authorization_state === 'NOT_AUTHORIZED' &&
        status.preparation_ready === true &&
        !unauthorizedProviderState && (
          <div>
            <label>
              <input
                type="checkbox"
                checked={confirmed}
                disabled={busy}
                onChange={event => setConfirmed(event.target.checked)}
              />
              I authorize preparation of an unsent Installation Manager
              inspection draft for this project's current approved MSR.
            </label>

            <button
              type="button"
              disabled={!confirmed || busy}
              onClick={() => { void authorize(); }}
            >
              {busy ? 'Recording authorization...' : 'Authorize inspection draft'}
            </button>
          </div>
        )}

      {actorRole === 'COMPTROLLER' && (
        <p className="muted">
          Comptroller access is read-only here. DocuSign sandbox authentication
          remains a separate, controlled workflow.
        </p>
      )}

      <p className="muted">
        This action does not create or send a DocuSign envelope, verify a
        signature, issue a final Receipt, or complete the project.
        Authorization recording is disabled unless the backend's development
        test gate is explicitly enabled.
      </p>

      {error && <p role="alert">{error}</p>}

      <button
        className="quiet"
        type="button"
        disabled={busy}
        onClick={() => setRevision(value => value + 1)}
      >
        Refresh inspection status
      </button>
    </section>
  );
}