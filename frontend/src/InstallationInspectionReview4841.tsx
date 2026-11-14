import React, { useCallback, useEffect, useState } from 'react';

type Queue = {
  project_id: string;
  read_only: true;
  status: string;
  pending_inspection_id: string | null;
  inspection_passed: boolean | null;
  inspection_notes?: string;
  inspection_recorded_at?: string;
  independent_review_recorded: boolean;
  review_decision: 'REJECTED' | 'INTERNAL_CANDIDATE_ACCEPTED' | null;
  trusted_installation_evidence: false;
  final_receipt_issuance_authorized: false;
  customer_delivery_verified: false;
  completion_authorized: false;
};

const statuses = [
  'PREREQUISITES_MISSING',
  'STORAGE_UNAVAILABLE',
  'NO_INSPECTION',
  'INSPECTION_UNVERIFIED',
  'PENDING_INDEPENDENT_REVIEW',
  'REVIEW_RECORDED_UNVERIFIED',
];

function validateQueue(value: unknown, projectId: string): value is Queue {
  if (!value || typeof value !== 'object') return false;
  const q = value as Record<string, unknown>;

  if (
    q.project_id !== projectId ||
    q.read_only !== true ||
    typeof q.status !== 'string' ||
    !statuses.includes(q.status) ||
    q.trusted_installation_evidence !== false ||
    q.final_receipt_issuance_authorized !== false ||
    q.customer_delivery_verified !== false ||
    q.completion_authorized !== false ||
    typeof q.independent_review_recorded !== 'boolean'
  ) return false;

  if (q.status === 'PENDING_INDEPENDENT_REVIEW') {
    return (
      typeof q.pending_inspection_id === 'string' &&
      q.pending_inspection_id.length > 0 &&
      typeof q.inspection_passed === 'boolean' &&
      typeof q.inspection_notes === 'string' &&
      q.inspection_notes.length >= 15 &&
      typeof q.inspection_recorded_at === 'string' &&
      q.independent_review_recorded === false
    );
  }

  return (
    q.pending_inspection_id === null &&
    (q.status === 'REVIEW_RECORDED_UNVERIFIED'
      ? (
        q.independent_review_recorded === true &&
        (
          q.review_decision === 'REJECTED' ||
          q.review_decision === 'INTERNAL_CANDIDATE_ACCEPTED'
        )
      )
      : q.review_decision === null)
  );
}

export function InstallationInspectionReview4841({
  projectId,
}: {
  projectId: string;
}) {
  const [queue, setQueue] = useState<Queue | null>(null);
  const [visible, setVisible] = useState(true);
  const [message, setMessage] = useState('');
  const [reason, setReason] = useState('');
  const [examined, setExamined] = useState(false);
  const [decision, setDecision] = useState<'accept' | 'reject'>('accept');
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);

  const load = useCallback(async (signal: AbortSignal) => {
    const response = await fetch(
      `/api/operational-projects/${encodeURIComponent(projectId)}/installation-inspection-review-queue/`,
      {
        method: 'GET',
        credentials: 'same-origin',
        cache: 'no-store',
        signal,
      },
    );

    if ([401, 403, 404].includes(response.status)) {
      return { unauthorized: true as const };
    }
    if (!response.ok) {
      throw new Error(`Inspection review request returned HTTP ${response.status}.`);
    }
    const payload: unknown = await response.json();
    if (!validateQueue(payload, projectId)) {
      throw new Error('Inspection review response did not match the required evidence fields.');
    }
    return { unauthorized: false as const, payload };
  }, [projectId]);

  useEffect(() => {
    const controller = new AbortController();
    setQueue(null);
    setVisible(true);
    setBusy(false);
    setReason('');
    setExamined(false);
    setDecision('accept');
    setMessage('Checking installation inspection review...');

    void load(controller.signal).then(result => {
      if (controller.signal.aborted) return;
      if (result.unauthorized) {
        setVisible(false);
      } else {
        setQueue(result.payload);
        setMessage('');
      }
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) {
        setQueue(null);
        setMessage(
          error instanceof Error
            ? error.message
            : 'Inspection review request failed unexpectedly.'
        );
      }
    });

    return () => controller.abort();
  }, [load, refresh]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      busy ||
      queue?.status !== 'PENDING_INDEPENDENT_REVIEW' ||
      !queue.pending_inspection_id ||
      reason.trim().length < 15 ||
      reason.trim().length > 2000 ||
      (decision === 'accept' && !examined)
    ) return;

    const inspectionId = queue.pending_inspection_id;
    setBusy(true);
    setMessage('Recording independent review...');
    try {
      const csrfResponse = await fetch('/api/csrf/', {
        credentials: 'same-origin',
        cache: 'no-store',
      });
      if (!csrfResponse.ok) throw new Error('CSRF request failed.');

      const csrfData: unknown = await csrfResponse.json();
      if (
        !csrfData ||
        typeof csrfData !== 'object' ||
        typeof (csrfData as Record<string, unknown>).csrfToken !== 'string'
      ) throw new Error('CSRF token unavailable.');

      const csrfToken = (csrfData as { csrfToken: string }).csrfToken;
      const response = await fetch(
        `/api/operational-projects/${encodeURIComponent(projectId)}/review-installation-inspection/`,
        {
          method: 'POST',
          credentials: 'same-origin',
          cache: 'no-store',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
          },
          body: JSON.stringify({
            inspection_id: inspectionId,
            accept: decision === 'accept',
            reason: reason.trim(),
            independently_examined: examined,
          }),
        },
      );

      if (!response.ok) {
        throw new Error(
          response.status === 403
            ? 'Independent review is not enabled or authorized for this session.'
            : `Review could not be recorded (${response.status}).`,
        );
      }

      const outcome: unknown = await response.json();
      if (
        !outcome ||
        typeof outcome !== 'object' ||
        (outcome as Record<string, unknown>).project_id !== projectId ||
        (outcome as Record<string, unknown>).source_authenticated !== false ||
        (outcome as Record<string, unknown>).trusted_installation_evidence !== false ||
        (outcome as Record<string, unknown>).final_receipt_issuance_authorized !== false ||
        (outcome as Record<string, unknown>).customer_delivery_verified !== false ||
        (outcome as Record<string, unknown>).completion_authorized !== false ||
        (outcome as Record<string, unknown>).status !== (
          decision === 'accept'
            ? 'INTERNAL_CANDIDATE_ACCEPTED'
            : 'INSPECTION_CANDIDATE_REJECTED'
        )
      ) {
        throw new Error('Review response failed verification.');
      }

      setQueue(null);
      setMessage('Internal review recorded. Source authentication remains pending.');
      setReason('');
      setExamined(false);
      setRefresh(value => value + 1);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : 'Review outcome unconfirmed. Refresh before retrying.',
      );
    } finally {
      setBusy(false);
    }
  }

  if (!visible) return null;

  return (
    <section aria-label="Independent installation inspection review">
      <h3>Independent Installation Inspection Review</h3>
      <p className="muted">
        Comptroller review of the selected project's installation inspection.
        This does not authenticate source documents or authorize project completion.
      </p>
      {message && <p role="status">{message}</p>}
      {queue?.status === 'NO_INSPECTION' && (
        <p>No installation inspection has been recorded for this project.</p>
      )}
      {queue?.status === 'REVIEW_RECORDED_UNVERIFIED' && (
        <>
          <p>
            <strong>Independent review decision: </strong>
            {queue.review_decision === 'REJECTED' ? (
              <strong
                style={{ color: '#B42318', fontWeight: 800 }}
                aria-label="Rejected"
              >
                REJECTED
              </strong>
            ) : (
              <strong
                style={{ color: '#087F75', fontWeight: 800 }}
                aria-label="Internal candidate accepted"
              >
                INTERNAL CANDIDATE ACCEPTED
              </strong>
            )}
          </p>
          <p>
            The review record is retained. Installation source evidence
            is not authenticated, and project completion remains blocked.
          </p>
        </>
      )}
      {queue?.status === 'INSPECTION_UNVERIFIED' && (
        <p>Inspection data failed verification. Administrative review required.</p>
      )}
      {queue?.status === 'STORAGE_UNAVAILABLE' && (
        <p>Inspection evidence storage is unavailable.</p>
      )}
      {queue?.status === 'PREREQUISITES_MISSING' && (
        <p>A current approved project record is required.</p>
      )}

      {queue?.status === 'PENDING_INDEPENDENT_REVIEW' && (
        <form onSubmit={event => void submit(event)}>
          <p>
            <strong style={{ color: '#9A6700', fontWeight: 800 }}>
              PENDING REVIEW
            </strong>
          </p>
          <p>
            <strong>Recorded inspection result: </strong>
            {queue.inspection_passed ? 'Passed (reported)' : 'Failed (reported)'}
          </p>
          <p>
            <strong>Inspection recorded: </strong>
            {queue.inspection_recorded_at}
          </p>
          <p>
            <strong>Installation Manager's notes:</strong>
          </p>
          <p>{queue.inspection_notes}</p>
          <p className="muted">
            Review the underlying installation evidence independently before
            selecting acceptance. The notes alone are not independent proof.
          </p>

          <label htmlFor="inspection-review-decision">
            Review decision
          </label>
          <select
            id="inspection-review-decision"
            value={decision}
            onChange={event => setDecision(
              event.target.value === 'reject' ? 'reject' : 'accept'
            )}
            disabled={busy}
          >
            <option value="accept">Accept internal inspection candidate</option>
            <option value="reject">Reject inspection candidate</option>
          </select>

          <label htmlFor="inspection-review-reason">
            Written review explanation
          </label>
          <textarea
            id="inspection-review-reason"
            value={reason}
            onChange={event => setReason(event.target.value)}
            minLength={15}
            maxLength={2000}
            rows={3}
            disabled={busy}
            required
          />

          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-start',
              gap: '0.65rem',
              width: 'fit-content',
              maxWidth: '100%',
              margin: '0.8rem 0',
              cursor: busy ? 'not-allowed' : 'pointer',
            }}
          >
            <input
              type="checkbox"
              checked={examined}
              onChange={event => setExamined(event.target.checked)}
              disabled={busy}
              style={{
                width: 'auto',
                height: 'auto',
                margin: 0,
                flex: '0 0 auto',
              }}
            />
            <span>I independently examined the underlying inspection evidence.</span>
          </label>

          <button
            type="submit"
            disabled={
              busy ||
              reason.trim().length < 15 ||
              (decision === 'accept' && !examined)
            }
          >
            Record independent review
          </button>
        </form>
      )}
      <p className="muted">
        FINAL Receipt issuance, customer delivery, and project completion
        remain blocked pending separate verified prerequisites.
      </p>
    </section>
  );
}
