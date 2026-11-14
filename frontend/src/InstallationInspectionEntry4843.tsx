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

export function InstallationInspectionEntry4843({
  api,
  projectId,
}: {
  api: Api;
  projectId: string;
}) {
  const [outcome, setOutcome] = useState<'pass' | 'fail'>('pass');
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [recorded, setRecorded] = useState(false);
  const [feedback, setFeedback] = useState('');

  useEffect(() => {
    setOutcome('pass');
    setNotes('');
    setBusy(false);
    setRecorded(false);
    setFeedback('');
  }, [projectId]);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const submittedProjectId = projectId;
    const submittedNotes = notes.trim();

    if (
      busy ||
      recorded ||
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

      {recorded ? (
        <p role="status">{feedback}</p>
      ) : (
        <form onSubmit={event => void submit(event)}>
          <label htmlFor="installation-inspection-outcome">
            Physical inspection result
          </label>
          <select
            id="installation-inspection-outcome"
            value={outcome}
            onChange={event => setOutcome(
              event.target.value === 'fail' ? 'fail' : 'pass'
            )}
            disabled={busy}
          >
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
            disabled={busy}
            required
            placeholder="Describe the physical inspection and its findings."
          />
          <p className="muted">
            Enter 15-2000 characters. The record cannot be edited after
            submission. A failed inspection cannot be accepted.
          </p>

          <button
            type="submit"
            disabled={
              busy ||
              notes.trim().length < 15 ||
              notes.trim().length > 2000
            }
          >
            {busy ? 'Recording...' : 'Record installation inspection'}
          </button>
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
