import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';

type API = <T,>(
  path: string, method?: string, data?: unknown
) => Promise<T>;

type ReviewQueue = {
  project_id: string;
  read_only: boolean;
  status: string;
  pending_inspection_id: string | null;
  review_submission_available: boolean;
  inspection_passed: boolean | null;
  inspection_notes?: string;
  inspection_recorded_at?: string;
  independent_review_recorded: boolean;
  review_decision: string | null;
  trusted_installation_evidence: boolean;
  final_receipt_issuance_authorized: boolean;
  customer_delivery_verified: boolean;
  completion_authorized: boolean;
};

const reviewMessages: Record<string, string> = {
  PREREQUISITES_MISSING:
    'A current approved Master Sales Record and completed installation are required.',
  STORAGE_UNAVAILABLE:
    'Inspection evidence storage is unavailable. No review can proceed.',
  NO_INSPECTION:
    'No Installation Manager inspection has been recorded.',
  INSPECTION_UNVERIFIED:
    'Inspection evidence could not be independently verified. Do not proceed.',
  PENDING_INDEPENDENT_REVIEW:
    'Installation Manager inspection recorded. Comptroller review is pending.',
  REVIEW_RECORDED_UNVERIFIED:
    'An internal Comptroller review has been recorded. DocuSign verification remains outstanding.',
};

export function ComptrollerInspectionReview5247({
  api, projectId,
}: {
  api: API;
  projectId: string;
}) {
  const [data, setData] = useState<ReviewQueue | null>(null);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [decision, setDecision] = useState('');
  const [reason, setReason] = useState('');
  const [examined, setExamined] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');

  async function submitReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const inspectionId = data?.pending_inspection_id;
    if (
      busy ||
      !data ||
      data.status !== 'PENDING_INDEPENDENT_REVIEW' ||
      data.review_submission_available !== true ||
      !inspectionId ||
      !['accept', 'reject'].includes(decision) ||
      reason.trim().length < 15 ||
      reason.trim().length > 2000 ||
      (decision === 'accept' && !examined)
    ) return;

    setBusy(true);
    setNotice('');
    setError('');
    try {
      const response = await api<{
        project_id: string;
        review_id: string;
        status: string;
        source_authenticated: false;
        trusted_installation_evidence: false;
        final_receipt_issuance_authorized: false;
        customer_delivery_verified: false;
        completion_authorized: false;
      }>(
        `operational-projects/${encodeURIComponent(projectId)}/review-installation-inspection/`,
        'POST',
        {
          inspection_id: inspectionId,
          accept: decision === 'accept',
          reason: reason.trim(),
          independently_examined: examined,
        }
      );

      if (
        response.project_id !== projectId ||
        !response.review_id ||
        response.status !== (
          decision === 'accept'
            ? 'INTERNAL_CANDIDATE_ACCEPTED'
            : 'INSPECTION_CANDIDATE_REJECTED'
        ) ||
        response.source_authenticated !== false ||
        response.trusted_installation_evidence !== false ||
        response.final_receipt_issuance_authorized !== false ||
        response.customer_delivery_verified !== false ||
        response.completion_authorized !== false
      ) {
        throw new Error('The review response could not be verified.');
      }
      setDecision('');
      setReason('');
      setExamined(false);
      setNotice('Internal review recorded. DocuSign verification remains required.');
      setRefresh(current => current + 1);
    } catch (cause) {
      setError(cause instanceof Error
        ? cause.message
        : 'Review could not be recorded.');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError('');

    void api<ReviewQueue>(
      `operational-projects/${encodeURIComponent(projectId)}/installation-inspection-review-queue/`
    ).then(value => {
      if (cancelled) return;
      const known = Object.prototype.hasOwnProperty.call(
        reviewMessages, value.status
      );
      if (
        value.project_id !== projectId ||
        value.read_only !== true ||
        typeof value.review_submission_available !== 'boolean' ||
        (value.review_submission_available === true &&
         value.status !== 'PENDING_INDEPENDENT_REVIEW') ||
        !known ||
        value.trusted_installation_evidence !== false ||
        value.final_receipt_issuance_authorized !== false ||
        value.customer_delivery_verified !== false ||
        value.completion_authorized !== false ||
        (value.status === 'PENDING_INDEPENDENT_REVIEW' &&
          (!value.pending_inspection_id ||
           value.independent_review_recorded !== false)) ||
        (value.status === 'REVIEW_RECORDED_UNVERIFIED' &&
          (value.independent_review_recorded !== true ||
           !['REJECTED', 'INTERNAL_CANDIDATE_ACCEPTED'].includes(
             value.review_decision ?? ''
           )))
      ) {
        setError('Inspection review response failed safety verification.');
        return;
      }
      setData(value);
    }).catch(reason => {
      if (!cancelled) {
        setError(
          reason instanceof Error ? reason.message :
          'Unable to load independent inspection review.'
        );
      }
    });
    return () => { cancelled = true; };
  }, [api, projectId, refresh]);

  const status = data?.status;
  const hasVerifiedCandidate = status === 'PENDING_INDEPENDENT_REVIEW' ||
    status === 'REVIEW_RECORDED_UNVERIFIED';

  return (
    <section aria-label="Independent Installation Inspection Review">
      <h4>Independent Installation Inspection Review</h4>
      <p className="muted">
        Comptroller-only review of the Installation Manager's recorded
        inspection. This section does not sign documents, issue the
        FINAL Receipt, or complete the project.
      </p>
      {!data && !error && <p>Checking inspection review status...</p>}
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {data && (
        <>
          <p role="status">
            <strong>Inspection review status: </strong>
            {reviewMessages[data.status]}
          </p>
          {hasVerifiedCandidate && (
            <>
              <p>
                <strong>Physical inspection result: </strong>
                {data.inspection_passed === true ? 'Passed' :
                 data.inspection_passed === false ? 'Failed' :
                 'Not verified'}
              </p>
              <p><strong>Installation Manager's inspection notes:</strong></p>
              <p style={{whiteSpace: 'pre-wrap'}}>
                {data.inspection_notes || 'Not available'}
              </p>
              {data.inspection_recorded_at && (
                <p className="muted">
                  Inspection recorded: {
                    new Date(data.inspection_recorded_at).toLocaleString()
                  }
                </p>
              )}
            </>
          )}
          {status === 'REVIEW_RECORDED_UNVERIFIED' && (
            <p>
              <strong>Comptroller review decision: </strong>
              {data.review_decision === 'REJECTED'
                ? 'Rejected — corrective action required'
                : 'Internal inspection candidate accepted — DocuSign verification still required'}
            </p>
          )}
          {status === 'PENDING_INDEPENDENT_REVIEW' &&
           data.review_submission_available === true ? (
            <form onSubmit={event => void submitReview(event)}>
              <h4>Record independent inspection review</h4>
              <label htmlFor="inspection-review-decision">
                Review decision
              </label>
              <select
                id="inspection-review-decision"
                value={decision}
                disabled={busy}
                required
                onChange={event => {
                  setDecision(event.target.value);
                  setExamined(false);
                }}
              >
                <option value="">Choose decision</option>
                <option value="accept">Accept internal candidate</option>
                <option value="reject">Reject internal candidate</option>
              </select>
              <label htmlFor="inspection-review-reason">
                Comptroller's review reason
              </label>
              <textarea
                id="inspection-review-reason"
                rows={4}
                value={reason}
                minLength={15}
                maxLength={2000}
                disabled={busy}
                required
                onChange={event => setReason(event.target.value)}
                placeholder="Describe the evidence examined and your decision."
              />
              <p className="muted">
                Enter 15-2000 characters. The decision cannot be edited
                after recording. Failed inspections cannot be accepted.
              </p>
              <label style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '10px',
                margin: '16px 0',
              }}>
                <input
                  type="checkbox"
                  style={{width: '18px', flexShrink: 0, margin: '3px 0 0'}}
                  checked={examined}
                  disabled={busy}
                  onChange={event => setExamined(event.target.checked)}
                />
                <span>
                  I independently examined the inspection evidence.
                </span>
              </label>
              <button
                type="submit"
                disabled={
                  busy ||
                  !['accept', 'reject'].includes(decision) ||
                  reason.trim().length < 15 ||
                  reason.trim().length > 2000 ||
                  (decision === 'accept' && !examined)
                }
              >
                {busy ? 'Recording review...' : 'Record independent review'}
              </button>
            </form>
          ) : (
            <p className="muted">
              Recording a Comptroller review is not enabled for this
              project and database. This screen is read-only.
            </p>
          )}
        </>
      )}
      <button
        type="button"
        className="quiet"
        onClick={() => setRefresh(current => current + 1)}
      >
        Refresh inspection review
      </button>
    </section>
  );
}
