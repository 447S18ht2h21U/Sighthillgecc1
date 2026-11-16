import React, { useEffect, useState } from 'react';

type Unit = {
  unit_id: string;
  brand: string;
  model_number: string;
  status: string;
  pending_id: string | null;
  serial_number: string | null;
  inspection_notes: string | null;
  captured_at: string | null;
};
type Queue = {
  project_id: string;
  status: string;
  units: Unit[];
  read_only: boolean;
  source_authenticated: boolean;
  trusted_installation_evidence: boolean;
  installation_authorized: boolean;
  final_receipt_issuance_authorized: boolean;
  customer_delivery_verified: boolean;
  completion_authorized: boolean;
};
const red = '#B42318';
const green = '#087F75';
const amber = '#9A6700';

// Current browser acceptance is inspection-review READ ONLY.
// A separate protected implementation and authorization are required
// before any decision-submission UI may become available.
const reviewSubmissionEnabled: boolean = false;

function label(status: string): string {
  switch (status) {
    case 'NO_INSPECTION': return 'NO INSPECTION RECORDED';
    case 'PENDING_INDEPENDENT_REVIEW': return 'AWAITING COMPTROLLER REVIEW';
    case 'REVIEW_RECORDED_UNVERIFIED': return 'INTERNAL REVIEW RECORDED — SOURCE UNVERIFIED';
    case 'EVIDENCE_INVALID': return 'INVALID EVIDENCE';
    default: return 'UNVERIFIED';
  }
}
function color(status: string): string {
  return status === 'PENDING_INDEPENDENT_REVIEW' ? amber
    : status === 'REVIEW_RECORDED_UNVERIFIED' ? amber : red;
}
function csrfCookie(): string {
  const item = document.cookie.split('; ')
    .find(part => part.startsWith('csrftoken='));
  return item ? decodeURIComponent(item.substring('csrftoken='.length)) : '';
}

export function EquipmentUnitReview4880({
  projectId,
}: {
  projectId: string;
}) {
  const [queue, setQueue] = useState<Queue | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState('');
  const [decision, setDecision] = useState<'reject' | 'accept'>('reject');
  const [reason, setReason] = useState('');
  const [examined, setExamined] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState('');

  useEffect(() => {
    let active = true;
    setQueue(null);
    setError('');
    setSelected('');
    setResult('');
    setLoading(true);
    void fetch(
      `/api/operational-projects/${encodeURIComponent(projectId)}/equipment-unit-review-queue/`,
      { credentials: 'same-origin' }
    ).then(async response => {
      if (response.status === 403) return null;
      if (!response.ok) throw new Error('Equipment review queue unavailable.');
      return await response.json() as Queue;
    }).then(data => {
      if (!active) return;
      if (data === null) {
        setError('Comptroller access required.');
        return;
      }
      if (
        data.project_id !== projectId || data.read_only !== true ||
        data.source_authenticated !== false ||
        data.trusted_installation_evidence !== false ||
        data.installation_authorized !== false ||
        data.final_receipt_issuance_authorized !== false ||
        data.customer_delivery_verified !== false ||
        data.completion_authorized !== false ||
        !Array.isArray(data.units)
      ) {
        throw new Error('Equipment review queue failed safety verification.');
      }
      setQueue(data);
    }).catch(err => {
      if (active) setError((err as Error).message);
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [projectId, result]);

  const pending = queue?.units.find(unit =>
    unit.pending_id === selected &&
    unit.status === 'PENDING_INDEPENDENT_REVIEW'
  );

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reviewSubmissionEnabled || !pending || busy ||
      reason.trim().length < 15 ||
      reason.trim().length > 2000 ||
      (decision === 'accept' && !examined)) return;

    const submittedProject = projectId;
    const submittedPending = pending.pending_id;
    if (!submittedPending) return;
    setBusy(true);
    setError('');
    try {
      await fetch('/api/csrf/', { credentials: 'same-origin' });
      const response = await fetch(
        `/api/operational-projects/${encodeURIComponent(submittedProject)}/review-equipment-unit-inspection/`,
        {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfCookie(),
          },
          body: JSON.stringify({
            pending_id: submittedPending,
            accept_candidate: decision === 'accept',
            review_reason: reason.trim(),
            independently_examined: examined,
          }),
        },
      );
      if (!response.ok) {
        throw new Error(`Independent review rejected by server (HTTP ${response.status}).`);
      }
      const data = await response.json() as {
        project_id: string;
        pending_id: string;
        status: string;
        source_authenticated: boolean;
        trusted_installation_evidence: boolean;
        installation_authorized: boolean;
        final_receipt_issuance_authorized: boolean;
        completion_authorized: boolean;
      };
      const expected = decision === 'accept'
        ? 'INTERNAL_CANDIDATE_ACCEPTED' : 'REJECTED';
      if (
        data.project_id !== submittedProject ||
        data.pending_id !== submittedPending ||
        data.status !== expected ||
        data.source_authenticated !== false ||
        data.trusted_installation_evidence !== false ||
        data.installation_authorized !== false ||
        data.final_receipt_issuance_authorized !== false ||
        data.completion_authorized !== false
      ) {
        throw new Error('Review response failed safety verification.');
      }
      setSelected('');
      setReason('');
      setExamined(false);
      setResult(expected);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="installation-completion-guidance"
      aria-label="Independent equipment-unit inspection review">
      <p>Comptroller-only equipment evidence status. Recording or
        internally reviewing an inspection does not authenticate an
        installation, authorize a FINAL Receipt, or complete a project.</p>
      <p role="status" style={{ fontWeight: 700, color: amber }}>
        READ-ONLY REVIEW QUEUE — decision submission is disabled in this
        browser-acceptance environment.
      </p>
      {loading && <p role="status">Loading equipment-unit review queue...</p>}
      {error && <p role="alert" style={{ color: red, fontWeight: 700 }}>{error}</p>}
      {result && (
        <p role="status" style={{
          fontWeight: 800,
          color: result === 'REJECTED' ? red : green,
        }}>
          {result === 'REJECTED' ? 'REJECTED' : 'INTERNAL CANDIDATE ACCEPTED'}
          {' — decision recorded; installation source unverified'}
        </p>
      )}
      {!loading && queue?.status === 'INVENTORY_UNAVAILABLE' &&
        <p role="alert" style={{ color: red, fontWeight: 800 }}>
          EQUIPMENT INVENTORY MISSING OR INVALID — REVIEW BLOCKED
        </p>}
      {queue?.status === 'QUEUE_AVAILABLE' && (
        <>
          <p role="status">
            {queue.units.length} equipment unit(s):{' '}
            {queue.units.filter(unit =>
              unit.status === 'PENDING_INDEPENDENT_REVIEW'
            ).length} awaiting review;{' '}
            {queue.units.filter(unit =>
              unit.status === 'REVIEW_RECORDED_UNVERIFIED'
            ).length} internally reviewed but unverified;{' '}
            {queue.units.filter(unit =>
              unit.status === 'NO_INSPECTION'
            ).length} without an inspection;{' '}
            {queue.units.filter(unit =>
              unit.status === 'EVIDENCE_INVALID'
            ).length} with invalid evidence.
          </p>
          <div style={{ overflowX: 'auto' }}>
            <table style={{
              width: '100%',
              tableLayout: 'fixed',
              borderCollapse: 'collapse',
            }}>
              <thead><tr>
                <th>Unit</th><th>Equipment</th><th>Serial (unverified)</th><th>Review status</th>
              </tr></thead>
              <tbody>{queue.units.map(unit => (
                <tr key={unit.unit_id}>
                  <td style={{ overflowWrap: 'anywhere', verticalAlign: 'top' }}>
                    {unit.unit_id}
                  </td>
                  <td style={{ overflowWrap: 'anywhere', verticalAlign: 'top' }}>
                    <strong>{unit.brand}</strong>
                    <div>{unit.model_number}</div>
                  </td>
                  <td style={{ overflowWrap: 'anywhere', verticalAlign: 'top' }}>
                    {unit.serial_number || 'Not verified'}
                  </td>
                  <td style={{ overflowWrap: 'anywhere', verticalAlign: 'top' }}>
                    <strong style={{ color: color(unit.status), fontWeight: 800 }}>
                      {label(unit.status)}
                    </strong>
                  </td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          {reviewSubmissionEnabled && queue.units.some(unit =>
            unit.status === 'PENDING_INDEPENDENT_REVIEW') && (
            <form onSubmit={event => void submit(event)}>
              <h4>Record Independent Decision</h4>
              <label>Pending physical unit
                <select required value={selected}
                  onChange={event => {
                    setSelected(event.target.value);
                    setReason('');
                    setExamined(false);
                    setResult('');
                  }}
                  disabled={busy}>
                  <option value="">Select pending inspection</option>
                  {queue.units.filter(unit =>
                    unit.status === 'PENDING_INDEPENDENT_REVIEW' &&
                    unit.pending_id).map(unit => (
                    <option key={unit.unit_id} value={unit.pending_id!}>
                      {unit.unit_id} — {unit.brand} {unit.model_number}
                    </option>
                  ))}
                </select>
              </label>
              {pending && (
                <div>
                  <p><strong>Recorded serial:</strong> {pending.serial_number}</p>
                  <p><strong>Inspection notes:</strong> {pending.inspection_notes}</p>
                  <p><strong>Observation time:</strong> {pending.captured_at}</p>
                </div>
              )}
              <label>Independent decision
                <select value={decision}
                  onChange={event => setDecision(
                    event.target.value === 'accept' ? 'accept' : 'reject'
                  )} disabled={busy}>
                  <option value="reject">Reject</option>
                  <option value="accept">Accept internal candidate</option>
                </select>
              </label>
              <label>Review reason (15–2000 characters)
                <textarea required minLength={15} maxLength={2000} rows={3}
                  value={reason} onChange={event => setReason(event.target.value)}
                  disabled={busy}/>
              </label>
              <label>
                <input type="checkbox" checked={examined}
                  onChange={event => setExamined(event.target.checked)}
                  disabled={busy}/>
                I independently examined the underlying inspection evidence
              </label>
              <button type="submit" disabled={
                busy || !pending ||
                reason.trim().length < 15 ||
                (decision === 'accept' && !examined)
              }>
                {busy ? 'Recording decision...' : 'Record Independent Decision'}
              </button>
            </form>
          )}
        </>
      )}
    </section>
  );
}
