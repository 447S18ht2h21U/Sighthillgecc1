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
  intent_id: string | null;
  provider_draft_created: boolean;
  provider_request_authorized: boolean;
  send_authorized: boolean;
  provider_signature_verified: boolean;
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

  const canAuthorize =
    actorRole === 'CEO' || actorRole === 'SALES_MANAGER';

  const canView =
    canAuthorize || actorRole === 'COMPTROLLER';

  useEffect(() => {
    let cancelled = false;

    setStatus(null);
    setError('');
    setConfirmed(false);

    if (!canView || !projectId) {
      return () => { cancelled = true; };
    }

    void api<Status>(
      `inspection-draft-intents/${encodeURIComponent(projectId)}/status/`
    ).then(result => {
      if (!cancelled) {
        if (result.project_id !== projectId) {
          setError('Inspection status project mismatch.');
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
            : 'Not yet verified. Complete the required installation source evidence and preparation review before authorizing a draft.'}
        </p>
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