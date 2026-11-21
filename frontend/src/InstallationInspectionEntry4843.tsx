import React, { useEffect, useState } from 'react';

type Api = <T,>(
  path: string,
  method?: string,
  data?: unknown,
) => Promise<T>;

type InspectionResponse = {
  project_id: string;
  inspection_id: string;
  status: string;
  source_authenticated: false;
  trusted_installation_evidence: false;
  final_receipt_issuance_authorized: false;
  customer_delivery_verified: false;
  completion_authorized: false;
};

type InspectionReadiness = {
  project_id: string;
  state: string;
  approved_msr: boolean;
  completed_schedule: boolean;
  inspection_already_recorded: boolean;
  answers_recorded_by_this_endpoint: boolean;
  provider_signature_verified: boolean;
  receipt_issuance_authorized: boolean;
  project_completion_authorized: boolean;
};

export function InstallationInspectionEntry4843({
  api,
  projectId,
}: {
  api: Api;
  projectId: string;
}) {
  const [outcome, setOutcome] = useState<'' | 'pass' | 'fail'>('');
  const [personallyInspected, setPersonallyInspected] = useState(false);
  const [readiness, setReadiness] = useState<InspectionReadiness | null>(null);
  const [readinessBusy, setReadinessBusy] = useState(true);
  const [readinessError, setReadinessError] = useState('');
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [recorded, setRecorded] = useState(false);
  const [feedback, setFeedback] = useState('');

  useEffect(() => {
    setOutcome('');
    setPersonallyInspected(false);
    setNotes('');
    setBusy(false);
    setRecorded(false);
    setFeedback('');
  }, [projectId]);

  useEffect(() => {
    let active = true;
    setReadiness(null);
    setReadinessBusy(true);
    setReadinessError('');

    void api<InspectionReadiness>(
      `im-inspection-workspace/${encodeURIComponent(projectId)}/`
    ).then(result => {
      if (!active) return;
      if (
        result.project_id !== projectId ||
        result.answers_recorded_by_this_endpoint !== false ||
        result.provider_signature_verified !== false ||
        result.receipt_issuance_authorized !== false ||
        result.project_completion_authorized !== false
      ) {
        setReadinessError('Inspection readiness failed safety verification.');
        return;
      }
      setReadiness(result);
    }).catch(error => {
      if (active) setReadinessError(
        error instanceof Error ? error.message :
        'Inspection readiness could not be checked.'
      );
    }).finally(() => {
      if (active) setReadinessBusy(false);
    });

    return () => { active = false; };
  }, [api, projectId]);

  const readyToRecord =
    readiness?.state === 'READY_FOR_INSPECTION_REVIEW' &&
    readiness.approved_msr === true &&
    readiness.completed_schedule === true &&
    readiness.inspection_already_recorded === false &&
    !readinessBusy &&
    !readinessError;

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const submittedProjectId = projectId;
    const submittedNotes = notes.trim();

    if (
      busy ||
      recorded ||
      !readyToRecord ||
      !personallyInspected ||
      (outcome !== 'pass' && outcome !== 'fail') ||
      !submittedProjectId ||
      submittedNotes.length < 15 ||
      submittedNotes.length > 2000
    ) return;

    setBusy(true);
    setFeedback('Recording installation inspection...');

    try {
      // Reuse the application's established authenticated API handler.
      const result = await api<InspectionResponse>(
        `operational-projects/${encodeURIComponent(submittedProjectId)}/record-installation-inspection/`,
        'POST',
        {
          inspection_passed: outcome === 'pass',
          notes: submittedNotes,
        },
      );

      if (
        result.project_id !== submittedProjectId ||
        typeof result.inspection_id !== 'string' ||
        !result.inspection_id ||
        result.status !== 'INSPECTION_CANDIDATE_RECORDED' ||
        result.source_authenticated !== false ||
        result.trusted_installation_evidence !== false ||
        result.final_receipt_issuance_authorized !== false ||
        result.customer_delivery_verified !== false ||
        result.completion_authorized !== false
      ) {
        throw new Error(
          'The server response could not confirm the inspection. ' +
          'Check the project before retrying.',
        );
      }

      setRecorded(true);
      setFeedback(
        'Installation inspection recorded as an internal candidate. ' +
        'Independent Comptroller review is still required.',
      );
    } catch (error) {
      setFeedback(
        error instanceof Error
          ? `Inspection not confirmed: ${error.message}`
          : 'Inspection not confirmed. Check the project before retrying.',
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      id="record-installation-inspection"
      className="installation-completion-guidance"
      aria-label="Record Installation Inspection"
    >
      <h3>Record Installation Inspection</h3>
      <p>
        Assigned Installation Manager only. Record the actual physical
        inspection after operational installation completion.
      </p>
      <p className="muted">
        This record is an internal inspection candidate, not authenticated
        proof of installation or permission to issue the FINAL Receipt.
      </p>
      {readinessBusy && <p role="status">Checking inspection readiness...</p>}
      {readinessError && <p role="alert">{readinessError}</p>}
      {!readinessBusy && !readinessError && !readyToRecord && !recorded && (
        <p role="status">
          {readiness?.state === 'INSPECTION_ALREADY_RECORDED'
            ? 'An inspection candidate is already recorded. Do not submit a duplicate.'
            : 'Inspection recording is unavailable until the approved MSR and completed installation requirements are confirmed.'}
        </p>
      )}

      {recorded ? (
        <p role="status">{feedback}</p>
      ) : (
        <form onSubmit={event => void submit(event)}>
          <label htmlFor="installation-inspection-outcome">
            Physical inspection result
          </label>
          <select
            id="installation-inspection-outcome"
            required
            value={outcome}
            onChange={event => setOutcome(
              event.target.value === 'fail' ? 'fail' : 'pass'
            )}
            disabled={busy || !readyToRecord}
          >
            <option value="">Choose result</option>
            <option value="pass">Passed</option>
            <option value="fail">Failed</option>
          </select>

          <label htmlFor="installation-inspection-notes">
            Installation Manager's inspection notes
          </label>
          <textarea
            id="installation-inspection-notes"
            rows={4}
            minLength={15}
            maxLength={2000}
            value={notes}
            onChange={event => setNotes(event.target.value)}
            disabled={busy || !readyToRecord}
            required
            placeholder="Describe the physical inspection and its findings."
          />
          <p className="muted">
            Enter 15-2000 characters. The record cannot be edited after
            submission. A failed inspection cannot be accepted.
          </p>

          <label style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '10px',
            margin: '16px 0',
            cursor: readyToRecord ? 'pointer' : 'default',
          }}>
            <input
              type="checkbox"
              style={{
                width: '18px',
                height: '18px',
                flexShrink: 0,
                margin: '3px 0 0',
                padding: 0,
                display: 'inline-block',
              }}
              checked={personallyInspected}
              onChange={event => setPersonallyInspected(event.target.checked)}
              disabled={busy || !readyToRecord}
              required
            />
            I personally performed this inspection and the findings
            accurately describe what I observed.
          </label>
          <button
            type="submit"
            disabled={
              busy ||
              !readyToRecord ||
              !personallyInspected ||
              (outcome !== 'pass' && outcome !== 'fail') ||
              notes.trim().length < 15 ||
              notes.trim().length > 2000
            }
          >
            {busy ? 'Recording...' : 'Record installation inspection'}
          </button>
          {!busy && !readyToRecord && (
            <p className="muted" role="status">
              Recording is unavailable until inspection readiness is confirmed.
              See the inspection readiness message above.
            </p>
          )}
          {!busy && readyToRecord &&
            (outcome === '' ||
             notes.trim().length < 15 ||
             notes.trim().length > 2000 ||
             !personallyInspected) && (
            <p className="muted" role="status">
              To enable Record installation inspection: choose Physical
              inspection result, enter 15-2000 characters in Installation
              Manager's inspection notes, and check the personal inspection
              confirmation.
            </p>
          )}
          {feedback && <p role="status">{feedback}</p>}
        </form>
      )}
      <p className="muted">
        An independent review is completed in Project Completion Review.
        Customer document release and project completion require separate
        verified evidence.
      </p>
    </section>
  );
}
