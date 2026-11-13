import React, { useEffect, useRef, useState } from 'react';

type CompletionRequirement = {
  key: string;
  label: string;
  status: 'READY' | 'BLOCKED';
  candidate_count: number;
  detail: string;
};

type ReceiptEvidence = {
  status: 'UNVERIFIED';
  approved_msr_id: string | null;
  valid_pdf_candidates: number;
  matching_outbox_intents: number;
  matching_local_observations: number;
  final_receipt_verified: false;
  provider_email_authenticated: false;
  customer_delivery_verified: false;
  completion_authorized: false;
  blockers: string[];
};

type EnvelopeStatus = {
  project_id: string;
  read_only: true;
  status: 'PREREQUISITES_MISSING' | 'SCHEMA_UNAVAILABLE'
    | 'ATTEMPTS_UNVERIFIED' | 'NO_ATTEMPTS';
  attempt_count: number;
  attempt_states: { state: string; count: number }[];
  provider_verified: false;
  installation_complete_qualified: false;
  completion_authorized: false;
  retry_authorized: false;
  reason: string;
};

type CompletionPreflight = {
  receipt_evidence?: ReceiptEvidence;
  evidence_requirements: CompletionRequirement[];
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
  const [envelopeStatus, setEnvelopeStatus] = useState<EnvelopeStatus | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const requestSequence = useRef(0);

  // Never display evidence belonging to a previously selected project.
  useEffect(() => {
    requestSequence.current += 1;
    setReport(null);
    setEnvelopeStatus(null);
    setError('');
    setLoading(false);
    setExpanded(false);
    return () => {
      requestSequence.current += 1;
    };
  }, [projectId]);

  async function review(forceRefresh = false) {
    if (loading) return;
    if (expanded && !forceRefresh) {
      requestSequence.current += 1;
      setExpanded(false);
      return;
    }

    const sequence = ++requestSequence.current;
    setReport(null);
    setEnvelopeStatus(null);
    setError('');
    setLoading(true);
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

      const requiredKeys = [
        'approved_msr', 'final_receipt', 'receipt_email',
        'completion_certificate', 'completion_transaction',
      ];
      const requirements = data.evidence_requirements;
      const receipt = data.receipt_evidence;
      const receiptRequired =
        data.status === 'COMPLETION_EVIDENCE_UNVERIFIED';
      const validReceipt =
        !receiptRequired ||
        (
          receipt != null &&
          receipt.status === 'UNVERIFIED' &&
          (receipt.approved_msr_id == null ||
            receipt.approved_msr_id === data.current_approved_msr_id) &&
          [
            receipt.valid_pdf_candidates,
            receipt.matching_outbox_intents,
            receipt.matching_local_observations,
          ].every(value => Number.isSafeInteger(value) && value >= 0) &&
          receipt.final_receipt_verified === false &&
          receipt.provider_email_authenticated === false &&
          receipt.customer_delivery_verified === false &&
          receipt.completion_authorized === false &&
          Array.isArray(receipt.blockers) &&
          receipt.blockers.every(value => typeof value === 'string')
        );

      if (
        !validReceipt ||
        !Array.isArray(requirements) ||
        requirements.length !== requiredKeys.length ||
        !requirements.every((item, index) =>
          item !== null &&
          typeof item === 'object' &&
          item.key === requiredKeys[index] &&
          typeof item.label === 'string' &&
          typeof item.detail === 'string' &&
          Number.isSafeInteger(item.candidate_count) &&
          item.candidate_count >= 0 &&
          (index === 0
            ? ['READY', 'BLOCKED'].includes(item.status)
            : item.status === 'BLOCKED')
        ) ||
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

      const envelopeResponse = await fetch(
        `/api/operational-projects/${encodeURIComponent(projectId)}/completion-signature-status/`,
        {
          method: 'GET',
          credentials: 'same-origin',
          cache: 'no-store',
        },
      );

      if (!envelopeResponse.ok) {
        throw new Error('Completion envelope status is unavailable.');
      }

      const envelope: EnvelopeStatus = await envelopeResponse.json();
      const total = Array.isArray(envelope.attempt_states)
        ? envelope.attempt_states.reduce(
            (sum, item) => sum + (
              item != null &&
              Number.isSafeInteger(item.count) &&
              item.count >= 0 ? item.count : 0
            ), 0
          )
        : -1;

      if (
        envelope.project_id !== projectId ||
        envelope.read_only !== true ||
        envelope.provider_verified !== false ||
        envelope.installation_complete_qualified !== false ||
        envelope.completion_authorized !== false ||
        envelope.retry_authorized !== false ||
        !Number.isSafeInteger(envelope.attempt_count) ||
        envelope.attempt_count < 0 ||
        !Array.isArray(envelope.attempt_states) ||
        !envelope.attempt_states.every(item =>
          item !== null &&
          typeof item.state === 'string' &&
          Number.isSafeInteger(item.count) &&
          item.count >= 0
        ) ||
        total !== envelope.attempt_count ||
        !['PREREQUISITES_MISSING', 'SCHEMA_UNAVAILABLE',
          'ATTEMPTS_UNVERIFIED', 'NO_ATTEMPTS'].includes(envelope.status) ||
        typeof envelope.reason !== 'string'
      ) {
        throw new Error('Completion envelope status failed the safety checks.');
      }

      if (sequence === requestSequence.current) {
        setReport(data);
        setEnvelopeStatus(envelope);
      }
    } catch (err) {
      if (sequence === requestSequence.current) {
        setError(err instanceof Error ? err.message : 'Completion review unavailable.');
      }
    } finally {
      if (sequence === requestSequence.current) {
        setLoading(false);
      }
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
          <button
            type="button"
            className="quiet"
            disabled={loading}
            onClick={event => {
              event.stopPropagation();
              void review(true);
            }}
          >
            {loading ? 'Refreshing evidence...' : 'Refresh evidence review'}
          </button>
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
              <strong>Completion evidence checklist</strong>
              <ul>
                {report.evidence_requirements.map(item => (
                  <li key={item.key}>
                    <strong>{item.label}: {item.status === 'READY' ? 'Prerequisite present' : 'Not verified'}</strong>
                    {' '}— {item.detail}
                    {item.candidate_count > 0 && (
                      <span> Candidate records: {item.candidate_count} (untrusted).</span>
                    )}
                  </li>
                ))}
              </ul>
              {report.receipt_evidence && (
                <>
                  <strong>Customer Receipt evidence</strong>
                  <ul>
                    <li>
                      Retained historical PDF candidates:
                      {' '}{report.receipt_evidence.valid_pdf_candidates}
                    </li>
                    <li>
                      Matching pending email requests:
                      {' '}{report.receipt_evidence.matching_outbox_intents}
                    </li>
                    <li>
                      Matching unverified sending observations:
                      {' '}{report.receipt_evidence.matching_local_observations}
                    </li>
                    <li>
                      Final Receipt: Not independently verified
                    </li>
                    <li>
                      Customer email sending: Not provider-authenticated
                    </li>
                  </ul>
                </>
              )}
              {envelopeStatus && (
                <>
                  <strong>DocuSign Completion Certificate activity</strong>
                  <p>
                    Recorded envelope attempts: {envelopeStatus.attempt_count}.
                    {' '}These records do not verify signatures.
                  </p>
                  {envelopeStatus.attempt_states.length > 0 && (
                    <ul>
                      {envelopeStatus.attempt_states.map((item, index) => (
                        <li key={`${item.state}-${index}`}>
                          {item.state.replaceAll('_', ' ').toLowerCase()}:
                          {' '}{item.count} unverified record(s)
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className="muted">{envelopeStatus.reason}</p>
                </>
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
