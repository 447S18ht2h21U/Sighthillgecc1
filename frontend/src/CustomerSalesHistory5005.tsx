import { useEffect, useState } from 'react';

type SalesHistoryRow = {
  id: number;
  previous_status: string | null;
  new_status: string;
  reason: string;
  changed_at: string;
  changed_by_id: string;
};

type SalesHistoryResponse = {
  project_id: string;
  sales_status: string | null;
  project_state: string;
  history: SalesHistoryRow[];
  history_limit: number;
};

const statusLabel = (value: string | null): string =>
  value === null
    ? 'Not yet classified'
    : value.charAt(0) + value.slice(1).toLowerCase();

export function CustomerSalesHistory5005({
  projectId,
  actorRole,
  onRecordStatus,
}: {
  projectId: string;
  actorRole: string;
  onRecordStatus: (id: string, status: string, reason: string) => Promise<void>;
}) {
  const [record, setRecord] = useState<SalesHistoryResponse | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const [newStatus, setNewStatus] = useState('');
  const [changeReason, setChangeReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [saveSuccess, setSaveSuccess] = useState('');

  const canChangeStatus =
    actorRole === 'CEO' || actorRole === 'SALES_MANAGER';

  useEffect(() => {
    if (!projectId) {
      setRecord(null);
      setError('');
      setBusy(false);
      return;
    }

    const controller = new AbortController();
    setRecord(null);
    setError('');
    setBusy(true);

    void (async () => {
      try {
        const response = await fetch(
          `/api/projects/${encodeURIComponent(projectId)}/sales-status/`,
          {
            credentials: 'same-origin',
            cache: 'no-store',
            signal: controller.signal,
            headers: { Accept: 'application/json' },
          },
        );

        if (!response.ok) {
          if (response.status === 404) {
            throw new Error(
              'Sales history is disabled or this project is unavailable.',
            );
          }
          if (response.status === 503) {
            throw new Error(
              'Sales history database is not ready. No records were changed.',
            );
          }
          throw new Error(`Sales history request failed (${response.status}).`);
        }

        const payload = (await response.json()) as SalesHistoryResponse;
        if (!controller.signal.aborted) setRecord(payload);
      } catch (cause) {
        if (!controller.signal.aborted) {
          setError(
            cause instanceof Error ? cause.message : 'Unable to load history.',
          );
        }
      } finally {
        if (!controller.signal.aborted) setBusy(false);
      }
    })();

    return () => controller.abort();
  }, [projectId, version]);

  async function submitStatus(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!record || !projectId || !canChangeStatus || saving) return;

    setSaveError('');
    setSaveSuccess('');

    if (!newStatus || newStatus === record.sales_status) {
      setSaveError('Choose a different sales status.');
      return;
    }
    if (changeReason.trim().length < 10) {
      setSaveError('Explain the change in at least 10 characters.');
      return;
    }

    setSaving(true);
    try {
      await onRecordStatus(projectId, newStatus, changeReason.trim());
      setSaveSuccess('Sales status recorded. Refreshing audit history.');
      setNewStatus('');
      setChangeReason('');
      setVersion(value => value + 1);
    } catch (cause) {
      setSaveError(
        cause instanceof Error ? cause.message : 'Status change was rejected.',
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <section aria-label="Sales opportunity history">
      <h2>Sales Opportunity History</h2>
      <p>
        Sales disposition is separate from operational project state,
        installation readiness, MSR approval, and completion.
      </p>

      {!projectId ? (
        <p role="status">
          Select a project in Customers &amp; Projects to view its history.
        </p>
      ) : (
        <>
          <p><strong>Project ID:</strong> {projectId}</p>
          <button
            type="button"
            disabled={busy}
            onClick={() => setVersion(value => value + 1)}
          >
            Refresh sales history
          </button>
          {busy && <p role="status">Loading sales history...</p>}
          {error && <p className="error" role="alert">{error}</p>}
          {record && (
            <>
              <p>
                <strong>Sales opportunity:</strong>{' '}
                {statusLabel(record.sales_status)}
              </p>
              <p>
                <strong>Operational project state:</strong>{' '}
                {record.project_state}
              </p>
              {canChangeStatus && (
                <form onSubmit={event => { void submitStatus(event); }}
                  style={{
                    marginTop: '1.5rem',
                    marginBottom: '1.5rem',
                    maxWidth: '42rem',
                  }}>
                  <h3>Record sales opportunity status</h3>
                  <p>
                    This changes only the commercial opportunity status.
                    It does not approve an MSR, authorize installation,
                    or complete a project.
                  </p>
                  <label>
                    New sales status
                    <select
                      value={newStatus}
                      disabled={saving}
                      onChange={event => setNewStatus(event.target.value)}
                      required
                    >
                      <option value="">Choose a status</option>
                      {['ACTIVE', 'WON', 'LOST', 'CANCELLED', 'INACTIVE']
                        .filter(value => value !== record.sales_status)
                        .map(value => (
                          <option key={value} value={value}>
                            {statusLabel(value)}
                          </option>
                        ))}
                    </select>
                  </label>
                  <label>
                    Reason for change
                    <textarea
                      value={changeReason}
                      disabled={saving}
                      onChange={event => setChangeReason(event.target.value)}
                      minLength={10}
                      required
                      rows={3}
                      placeholder="Explain the customer or sales decision"
                    />
                  </label>
                  <button
                    type="submit"
                    disabled={saving || !newStatus || changeReason.trim().length < 10}
                  >
                    {saving ? 'Recording...' : 'Record sales status'}
                  </button>
                  {saveError && <p role="alert" className="error">{saveError}</p>}
                  {saveSuccess && <p role="status">{saveSuccess}</p>}
                </form>
              )}
              <h3>Sales-status change history</h3>
              {record.history.length === 0 ? (
                <p>No recorded sales-status changes for this project.</p>
              ) : (
                <div style={{ overflowX: 'auto', marginTop: '0.75rem' }}>
                  <table style={{
                    width: '100%',
                    minWidth: '850px',
                    borderCollapse: 'separate',
                    borderSpacing: '0 0.5rem',
                  }}>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Previous status</th>
                        <th>New status</th>
                        <th>Reason</th>
                        <th>Recorded by (user ID)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {record.history.map(row => (
                        <tr key={row.id}>
                          <td>{new Date(row.changed_at).toLocaleString('en-US', {
                            timeZone: 'America/New_York',
                            dateStyle: 'medium',
                            timeStyle: 'short',
                          })} ET</td>
                          <td>{statusLabel(row.previous_status)}</td>
                          <td>{statusLabel(row.new_status)}</td>
                          <td style={{ minWidth: '230px', whiteSpace: 'normal' }}>{row.reason}</td>
                          <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{row.changed_by_id}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {record.history.length >= record.history_limit && (
                <p>
                  Showing the latest {record.history_limit} entries.
                  Older records remain retained.
                </p>
              )}
            </>
          )}
        </>
      )}

      <p>
        History entries are read-only. Lost, cancelled, and inactive sales
        opportunities remain in customer history.
      </p>
    </section>
  );
}
