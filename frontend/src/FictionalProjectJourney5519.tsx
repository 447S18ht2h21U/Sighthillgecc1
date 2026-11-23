import { useEffect, useState } from 'react';

type Assessment = Record<string, unknown>;

type StatusResult = {
  data: Assessment | null;
  error: string;
};

type Stage = {
  title: string;
  status: string;
  description: string;
  target?: string;
  blockers?: string[];
};

const empty = (): StatusResult => ({ data: null, error: '' });

function isObject(value: unknown): value is Assessment {
  return typeof value === 'object' && value !== null
    && !Array.isArray(value);
}

function blockers(data: Assessment | null): string[] {
  if (!data) return [];
  const value = Array.isArray(data.blockers)
    ? data.blockers
    : data.blocking_reasons;
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is string => typeof item === 'string'
  ).slice(0, 12);
}

async function getStatus(
  url: string,
  signal: AbortSignal
): Promise<StatusResult> {
  try {
    const response = await fetch(url, {
      method: 'GET',
      credentials: 'same-origin',
      cache: 'no-store',
      signal,
    });
    if (!response.ok) {
      return {
        data: null,
        error: response.status === 401 || response.status === 403
          ? 'Not available to your current role.'
          : 'Status unavailable (HTTP ' + response.status + ').',
      };
    }
    const value: unknown = await response.json();
    return isObject(value)
      ? { data: value, error: '' }
      : { data: null, error: 'Invalid status response.' };
  } catch {
    return signal.aborted
      ? empty()
      : { data: null, error: 'Could not retrieve status.' };
  }
}

export default function FictionalProjectJourney5519({
  projectId,
  approved,
  projectState,
  completionVisible,
  onOpenInstallation,
  onOpenPayments,
}: {
  projectId: string;
  approved: boolean;
  projectState: string;
  completionVisible: boolean;
  onOpenInstallation: () => void;
  onOpenPayments?: () => void;
}) {
  const [installation, setInstallation] = useState<StatusResult>(empty);
  const [completion, setCompletion] = useState<StatusResult>(empty);
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    setLoading(true);
    setInstallation(empty());
    setCompletion(empty());

    const base = '/api/operational-projects/'
      + encodeURIComponent(projectId);

    const first = getStatus(
      base + '/installation-eligibility/',
      controller.signal
    );

    const second = completionVisible
      ? getStatus(base + '/completion-preflight/', controller.signal)
      : Promise.resolve<StatusResult>({
          data: null,
          error: 'An authorized completion reviewer is required.',
        });

    Promise.all([first, second]).then(([i, c]) => {
      if (!active) return;
      setInstallation(i);
      setCompletion(c);
      setLoading(false);
    });

    return () => {
      active = false;
      controller.abort();
    };
  }, [projectId, completionVisible, refresh]);

  // Only explicit backend authorization indicators can report success.
  // Never interpret an empty blocker list as authorization.
  const eligible =
    installation.data?.eligible === true ||
    installation.data?.installation_eligible === true;

  const completed =
    completion.data?.project_completed === true &&
    completion.data?.completion_authorized === true;

  const stages: Stage[] = [
    {
      title: '1. Sale and approved MSR',
      status: approved ? 'Approved' : 'Approval required',
      description: approved
        ? 'Approved MSR exists. Review scope, equipment, pricing and terms.'
        : 'An approved MSR is required.',
    },
    {
      title: '2. Contract and Invoice',
      status: 'Review required',
      description: 'Prepared PDFs are not signed documents. Review document versions and contents.',
      target: 'journey-documents-5519',
    },
    {
      title: '3. Customer signing',
      status: 'Authentication required',
      description: 'Commercial DocuSign authentication is not connected. Fictional signatures cannot authorize installation.',
      target: 'journey-signing-5519',
    },
    {
      title: '4. Deposit and installation',
      status: loading ? 'Checking'
        : installation.error ? 'Status unavailable'
        : eligible ? 'Eligibility reported' : 'Not authorized',
      description: installation.error ||
        'Installation requires authenticated customer Contract and Invoice signatures, the applicable waiting period and verified payment.',
      blockers: blockers(installation.data),
    },
    {
      title: '5. Completion and final Receipt',
      status: loading ? 'Checking'
        : completion.error ? 'Status unavailable'
        : completed ? 'Completion reported' : 'Not completed',
      description: completion.error ||
        'Requires verified work, full payment, final Receipt email delivery and the completed DocuSign certificate.',
      target: completionVisible ? 'journey-completion-5519' : undefined,
      blockers: blockers(completion.data),
    },
    {
      title: '6. Payroll and financial reporting',
      status: 'Separate review',
      description: 'Use the existing payroll and financial reporting workspaces. Fictional scenarios are not accounting records.',
    },
  ];

  return (
    <section aria-label="Fictional Project Journey" style={{
      margin: '18px 0',
      padding: 18,
      background: '#F7F8F5',
      border: '2px solid #087F75',
      borderRadius: 8,
    }}>
      <h3>Project 104 - End-to-End Journey</h3>
      <p><strong>FICTIONAL PROJECT - OPERATIONAL STATUS REVIEW</strong></p>
      <p>
        This dashboard displays existing project information and read-only
        backend assessments. Viewing it never authorizes a transaction.
      </p>
      <p>
        <strong>Project:</strong> {projectState}
        {' | '}
        <strong>Approved MSR:</strong> {approved ? 'Yes' : 'No'}
      </p>

      <button type="button" className="quiet" disabled={loading}
        onClick={() => setRefresh(value => value + 1)}>
        {loading ? 'Checking project status...' : 'Refresh project status'}
      </button>

      <div style={{ marginTop: 14 }}>
        {stages.map(stage => (
          <div key={stage.title} style={{
            border: '1px solid #D7E3E7',
            borderRadius: 7,
            background: '#fff',
            padding: 12,
            marginBottom: 10,
          }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 10,
            }}>
              <strong>{stage.title}</strong>
              <span style={{
                border: '1px solid #D7E3E7',
                borderRadius: 5,
                padding: '4px 8px',
                fontWeight: 700,
              }}>{stage.status}</span>
            </div>
            <p style={{ margin: '8px 0' }}>{stage.description}</p>
            {stage.blockers && stage.blockers.length > 0 && (
              <div>
                <strong>Outstanding requirements</strong>
                <ul>
                  {stage.blockers.map((reason, index) => (
                    <li key={index}>{reason}</li>
                  ))}
                </ul>
              </div>
            )}
            {stage.title === '4. Deposit and installation' && (
              <div style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 8,
                margin: '10px 0',
              }}>
                <button
                  type="button"
                  className="quiet"
                  onClick={onOpenInstallation}
                >
                  Review Installation Scheduling
                </button>
                {onOpenPayments && (
                  <button
                    type="button"
                    className="quiet"
                    onClick={onOpenPayments}
                  >
                    Review Customer Payments
                  </button>
                )}
              </div>
            )}
            {stage.target && (
              <a href={'#' + stage.target}>Open existing review</a>
            )}
          </div>
        ))}
      </div>
      <p>
        <strong>
          No signatures, payments, installation, completion or payroll
          are authorized by this dashboard.
        </strong>
      </p>
    </section>
  );
}
