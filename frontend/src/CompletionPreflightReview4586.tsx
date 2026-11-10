import React, { useState } from 'react';

type CompletionPreflight = {
  project_id: string;
  status: string;
  read_only: boolean;
  current_approved_msr_id?: string;
  receipt_candidates?: number;
  unverified_email_observations?: number;
  certificate_candidates?: number;
  receipt_email_authenticated: boolean;
  docusign_completion_authenticated: boolean;
  satisfaction_survey_required: boolean;
  completion_authorized: boolean;
  project_completed: boolean;
  blockers: string[];
};

export function CompletionPreflightReview4586({
  projectId,
  projectCode,
}: {
  projectId: string;
  projectCode: string;
}) {
  const [report, setReport] = useState<CompletionPreflight | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  async function review() {
    if (loading) return;
    if (expanded) {
      setExpanded(false);
      return;
    }

    setLoading(true);
    setError('');
    setReport(null);
    setExpanded(true);

    try {
      const response = await fetch(
        `/api/operational-projects/${encodeURIComponent(projectId)}/completion-preflight/`,
        {
          method: 'GET',
          credentials: 'same-origin',
          cache: 'no-store',
        },
      );

      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          throw new Error('Completion evidence review is not authorized for this account.');
        }
        if (response.status === 404) {
          throw new Error('Project is unavailable in your authorized operational scope.');
        }
        throw new Error(`Completion evidence could not be retrieved (${response.status}).`);
      }

      const data: CompletionPreflight = await response.json();

      if (
        data.project_id !== projectId ||
        data.read_only !== true ||
        data.completion_authorized !== false ||
        data.project_completed !== false ||
        data.receipt_email_authenticated !== false ||
        data.docusign_completion_authenticated !== false ||
        data.satisfaction_survey_required !== false ||
        !Array.isArray(data.blockers) ||
        !data.blockers.every(item => typeof item === 'string') ||
        !['COMPLETION_EVIDENCE_UNVERIFIED', 'EVIDENCE_STORAGE_UNAVAILABLE', 'COMPLETION_PREREQUISITES_MISSING'].includes(data.status)
      ) {
        throw new Error('Completion evidence response failed the safety checks.');
      }

      setReport(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Completion review unavailable.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="dashboard-completion-preflight">
      <button
        type="button"
        className="quiet veridian-completion-review-button"
        disabled={loading}
        aria-expanded={expanded}
        aria-label={`Review completion evidence for ${projectCode}`}
        onClick={event => {
          event.stopPropagation();
          void review();
        }}
        onKeyDown={event => event.stopPropagation()}
      >
        {loading ? 'Checking completion evidence...' :
          expanded ? 'Hide completion evidence' : 'Review completion evidence'}
      </button>

      {expanded && (
        <div
          className="dashboard-selected-project-guidance"
          onClick={event => event.stopPropagation()}
        >
          <h4>Administrative Project Completion</h4>
          <p><strong>Completion not authorized</strong></p>
          <p className="muted">
            This read-only review does not change installation status or
            authorize project completion.
          </p>

          {loading && <p role="status">Loading completion evidence...</p>}
          {error && <p role="alert">{error}</p>}

          {report && (
            <>
              {report.status === 'COMPLETION_PREREQUISITES_MISSING' ? (
                <p>Project prerequisites must be satisfied before completion evidence can be assessed.</p>
              ) : report.status === 'EVIDENCE_STORAGE_UNAVAILABLE' ? (
                <p>Completion evidence storage is unavailable pending migration and verification.</p>
              ) : (
                <ul>
                  <li>Retained Receipt PDF candidates: {report.receipt_candidates ?? 0} (not verified final Receipts)</li>
                  <li>Email observations: {report.unverified_email_observations ?? 0} (not authenticated delivery)</li>
                  <li>Completion Certificate candidates: {report.certificate_candidates ?? 0} (not authenticated DocuSign completion)</li>
                </ul>
              )}
              <p>Customer Satisfaction Survey: Optional</p>
              <strong>Outstanding completion requirements</strong>
              <ul>
                {report.blockers.map((reason, index) => (
                  <li key={index}>{reason}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}
