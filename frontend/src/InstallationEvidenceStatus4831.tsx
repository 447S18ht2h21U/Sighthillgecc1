import React, { useEffect, useState } from 'react';

type EvidenceStatus = {
  project_id: string;
  read_only: true;
  status: string;
  installation_schedule_completed: boolean;
  physical_unit_count: number;
  verified_inspection_candidate_count: number;
  internal_acceptance_candidate_verified: boolean;
  installation_source_integrity_verified: boolean;
  installation_provenance_status: string;
  installation_source_authenticated: false;
  trusted_installation_evidence: false;
  final_receipt_issuance_authorized: false;
  provider_email_authenticated: false;
  customer_delivery_verified: false;
  completion_authorized: false;
  blockers: string[];
};

const allowedStatuses = [
  'PREREQUISITES_MISSING',
  'SCHEMA_UNAVAILABLE',
  'EVIDENCE_REVIEW_RELEASE_BLOCKED',
  'EVIDENCE_VERIFICATION_FAILED',
];

const allowedProvenance = [
  'UNVERIFIED',
  'INTERNAL_ACCEPTANCE_CANDIDATE_MISSING',
  'AWAITING_AUTHENTICATED_INSTALLATION_PROOF',
  'SOURCE_ARTIFACT_RETAINED_UNAUTHENTICATED',
];

function validReport(
  value: unknown,
  projectId: string,
): value is EvidenceStatus {
  if (!value || typeof value !== 'object') return false;

  const r = value as Record<string, unknown>;

  if (
    r.project_id !== projectId ||
    r.read_only !== true ||
    typeof r.status !== 'string' ||
    !allowedStatuses.includes(r.status) ||
    typeof r.installation_provenance_status !== 'string' ||
    !allowedProvenance.includes(r.installation_provenance_status)
  ) return false;

  const fields = [
    'installation_schedule_completed',
    'internal_acceptance_candidate_verified',
    'installation_source_integrity_verified',
  ];

  if (fields.some(field => typeof r[field] !== 'boolean')) {
    return false;
  }

  const denied = [
    'installation_source_authenticated',
    'trusted_installation_evidence',
    'final_receipt_issuance_authorized',
    'provider_email_authenticated',
    'customer_delivery_verified',
    'completion_authorized',
  ];

  if (denied.some(field => r[field] !== false)) return false;

  const count = r.physical_unit_count;
  const verified = r.verified_inspection_candidate_count;

  if (
    !Number.isSafeInteger(count) ||
    !Number.isSafeInteger(verified) ||
    (count as number) < 0 ||
    (verified as number) < 0 ||
    (verified as number) > (count as number)
  ) return false;

  if (
    !Array.isArray(r.blockers) ||
    !r.blockers.every(item => typeof item === 'string')
  ) return false;

  if (
    r.status !== 'EVIDENCE_REVIEW_RELEASE_BLOCKED' &&
    (
      r.installation_schedule_completed !== false ||
      r.physical_unit_count !== 0 ||
      r.verified_inspection_candidate_count !== 0 ||
      r.internal_acceptance_candidate_verified !== false ||
      r.installation_source_integrity_verified !== false ||
      r.installation_provenance_status !== 'UNVERIFIED'
    )
  ) return false;

  if (
    r.installation_source_integrity_verified === true &&
    (
      r.internal_acceptance_candidate_verified !== true ||
      r.installation_provenance_status !==
        'SOURCE_ARTIFACT_RETAINED_UNAUTHENTICATED'
    )
  ) return false;

  if (
    r.installation_provenance_status ===
      'SOURCE_ARTIFACT_RETAINED_UNAUTHENTICATED' &&
    (
      r.installation_source_integrity_verified !== true ||
      r.internal_acceptance_candidate_verified !== true
    )
  ) return false;

  if (
    r.installation_provenance_status ===
      'AWAITING_AUTHENTICATED_INSTALLATION_PROOF' &&
    (
      r.internal_acceptance_candidate_verified !== true ||
      r.installation_source_integrity_verified !== false
    )
  ) return false;

  return true;
}

function label(status: string): string {
  switch (status) {
    case 'SOURCE_ARTIFACT_RETAINED_UNAUTHENTICATED':
      return 'Source document retained; authenticity not established';
    case 'AWAITING_AUTHENTICATED_INSTALLATION_PROOF':
      return 'Independent source authentication pending';
    case 'INTERNAL_ACCEPTANCE_CANDIDATE_MISSING':
      return 'Independent inspection acceptance incomplete';
    case 'SCHEMA_UNAVAILABLE':
      return 'Evidence storage unavailable';
    case 'PREREQUISITES_MISSING':
      return 'Current approved project record required';
    case 'EVIDENCE_VERIFICATION_FAILED':
      return 'Evidence verification failed; review required';
    default:
      return 'Installation evidence remains unverified';
  }
}

export function InstallationEvidenceStatus4831({
  projectId,
}: {
  projectId: string;
}) {
  const [report, setReport] = useState<EvidenceStatus | null>(null);
  const [message, setMessage] = useState('Checking installation evidence...');
  const [visible, setVisible] = useState(true);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    setReport(null);
    setMessage('Checking installation evidence...');
    setVisible(true);

    void (async () => {
      try {
        const response = await fetch(
          `/api/operational-projects/${encodeURIComponent(projectId)}/installation-evidence-status/`,
          {
            method: 'GET',
            credentials: 'same-origin',
            cache: 'no-store',
            signal: controller.signal,
          },
        );

        if (
          response.status === 401 ||
          response.status === 403 ||
          response.status === 404
        ) {
          if (!controller.signal.aborted) setVisible(false);
          return;
        }

        if (!response.ok) {
          throw new Error('Installation evidence request failed.');
        }

        const data: unknown = await response.json();

        if (!validReport(data, projectId)) {
          throw new Error('Installation evidence response is invalid.');
        }

        if (!controller.signal.aborted) {
          setReport(data);
          setMessage('');
        }
      } catch {
        if (!controller.signal.aborted) {
          setReport(null);
          setMessage('Installation evidence unavailable or unverified.');
        }
      }
    })();

    return () => controller.abort();
  }, [projectId, refresh]);

  if (!visible) return null;

  return (
    <section aria-label="Installation evidence status">
      <h3>Installation Inspection &amp; Acceptance</h3>

      <p className="muted">
        Read-only evidence review. No installation certification,
        FINAL Receipt issuance or customer delivery authorization.
      </p>

      <button
        type="button"
        className="quiet"
        onClick={() => setRefresh(value => value + 1)}
      >
        Refresh installation evidence
      </button>

      {message && <p role="status">{message}</p>}

      {report && (
        <div role="status">
          <p><strong>{label(
            report.status === 'EVIDENCE_REVIEW_RELEASE_BLOCKED'
              ? report.installation_provenance_status
              : report.status
          )}</strong></p>

          <p>
            Installation schedule:
            {' '}
            {report.installation_schedule_completed
              ? 'Recorded complete; physical completion not independently authenticated'
              : 'Completion not established'}
          </p>

          <p>
            Equipment-unit inspections (verified / recorded units):
            {' '}
            {report.verified_inspection_candidate_count}
            {' / '}
            {report.physical_unit_count}
          </p>

          <p>
            Independent acceptance review:
            {' '}
            {report.internal_acceptance_candidate_verified
              ? 'Internal candidate verified'
              : 'Not verified'}
          </p>

          <p>
            Retained source document:
            {' '}
            {report.installation_source_integrity_verified
              ? 'Stored bytes and fingerprint verified'
              : 'Missing or unverified'}
          </p>

          <p>
            Source authentication: Not established
          </p>

          <p>
            FINAL Receipt issuance: Blocked
          </p>

          <p>
            Customer delivery and project completion: Blocked
          </p>

          {report.blockers.length > 0 && (
            <details>
              <summary>Evidence requirements and blockers</summary>
              <ul>
                {report.blockers.map((blocker, index) => (
                  <li key={`${index}-${blocker}`}>{blocker}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </section>
  );
}
