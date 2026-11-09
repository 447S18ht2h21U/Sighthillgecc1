/**
 * Read-only display of existing project prerequisite checks.
 *
 * A passing prerequisite is not installation authorization.
 * Receipt delivery and DocuSign completion require separate
 * independently verified evidence.
 */

export type WorkflowEvidenceStatus =
  | 'VERIFIED'
  | 'CHECK_PASSED'
  | 'BLOCKED'
  | 'NOT_EVALUATED';

export type ProjectWorkflowEvidence = {
  read_only: boolean;
  evidence_source: string;
  installation_authorized: boolean;
  project_completion_authorized: boolean;
  statuses: Record<string, string>;
};

type WorkflowItem = {
  key: string;
  title: string;
  explanation: string;
};

const items: readonly WorkflowItem[] = [
  {
    key: 'approved_msr',
    title: 'Current approved Master Sales Record',
    explanation: 'Check that the project has its own current approved MSR.',
  },
  {
    key: 'contract_signature',
    title: 'Contract signature evidence',
    explanation: 'A generated Agreement is not proof of signature.',
  },
  {
    key: 'cancellation_deadline',
    title: 'Cancellation deadline',
    explanation: 'Applicable cancellation requirements must be satisfied.',
  },
  {
    key: 'waiting_period',
    title: 'Installation waiting period',
    explanation: 'A completed signature alone does not end the waiting period.',
  },
  {
    key: 'payment_readiness',
    title: 'Installation payment prerequisite',
    explanation: 'Verified payment or a properly approved exception is required.',
  },
  {
    key: 'installation_authorization',
    title: 'Full installation authorization',
    explanation: 'Other scheduling, assignment, and equipment controls remain separate.',
  },
  {
    key: 'final_invoice_delivery',
    title: 'Final Invoice and delivery',
    explanation: 'Equipment identification, final Invoice and delivery require their own evidence.',
  },
  {
    key: 'receipt_delivery',
    title: 'Final Receipt and customer email',
    explanation: 'Retained final Receipt and authenticated sending evidence are mandatory.',
  },
  {
    key: 'completed_docusign',
    title: 'Completed DocuSign certificate',
    explanation: 'GECC must receive and retain the verified completed certificate for this project.',
  },
  {
    key: 'project_completion',
    title: 'Project completion authorization',
    explanation: 'Completion remains unavailable until all mandatory controls are implemented and satisfied. Customer survey is optional.',
  },
];

const allowed = new Set<WorkflowEvidenceStatus>([
  'VERIFIED',
  'CHECK_PASSED',
  'BLOCKED',
  'NOT_EVALUATED',
]);

function safeStatus(
  evidence: ProjectWorkflowEvidence | undefined,
  key: string,
): WorkflowEvidenceStatus {
  if (
    !evidence ||
    evidence.read_only !== true ||
    evidence.evidence_source !== 'EXISTING_PREREQUISITE_CHECKS' ||
    evidence.installation_authorized !== false ||
    evidence.project_completion_authorized !== false ||
    !evidence.statuses ||
    typeof evidence.statuses !== 'object' ||
    Array.isArray(evidence.statuses)
  ) {
    return 'NOT_EVALUATED';
  }

  if (key === 'project_completion') {
    return 'BLOCKED';
  }

  // Never infer a completed delivery, signature, or authorization
  // from a prerequisite-check report.
  if (
    key === 'installation_authorization' ||
    key === 'final_invoice_delivery' ||
    key === 'receipt_delivery' ||
    key === 'completed_docusign'
  ) {
    return 'NOT_EVALUATED';
  }

  const raw = evidence.statuses[key];
  if (typeof raw !== 'string' || !allowed.has(raw as WorkflowEvidenceStatus)) {
    return 'NOT_EVALUATED';
  }

  if (raw === 'VERIFIED' && key !== 'approved_msr') {
    return 'NOT_EVALUATED';
  }

  if (raw === 'CHECK_PASSED' && key === 'approved_msr') {
    return 'NOT_EVALUATED';
  }

  return raw as WorkflowEvidenceStatus;
}

function statusLabel(status: WorkflowEvidenceStatus): string {
  switch (status) {
    case 'VERIFIED':
      return 'Verified';
    case 'CHECK_PASSED':
      return 'Prerequisite check passed';
    case 'BLOCKED':
      return 'Blocked';
    default:
      return 'Not evaluated';
  }
}

export function ProjectDocumentWorkflowStatus({
  projectCode,
  evidence,
}: {
  projectCode: string;
  evidence?: ProjectWorkflowEvidence;
}) {
  return (
    <details className="dashboard-selected-project-guidance">
      <summary>Document &amp; Workflow Status</summary>
      <p>
        Project {projectCode}. This display is read-only and does not
        approve installation or project completion.
      </p>
      <ul aria-label={`Document workflow checks for ${projectCode}`}>
        {items.map((item) => {
          const status = safeStatus(evidence, item.key);
          return (
            <li key={item.key}>
              <strong>{item.title}: {statusLabel(status)}</strong>
              <p>{item.explanation}</p>
            </li>
          );
        })}
      </ul>
      <p>
        A prerequisite check passing does not establish installation
        permission. Completion requires independently verified Receipt
        delivery and completed DocuSign evidence.
      </p>
    </details>
  );
}