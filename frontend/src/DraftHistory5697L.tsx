import { useState } from 'react';

type Change5697L = {
  before: unknown;
  after: unknown;
};

type Entry5697L = {
  id: string;
  sequence: number;
  msr_id: string | null;
  version: number | null;
  edit_sequence: number | null;
  actor_name: string;
  actor_role: string;
  saved_at: string;
  changed_fields: Record<string, Change5697L> | null;
  snapshot: Record<string, unknown> | null;
  has_explicit_comparison: boolean;
};

export type DraftHistoryResponse5697L = {
  project_id: string;
  entries: Entry5697L[];
  limit: number;
  more_available: boolean;
};

function displayValue5697L(value: unknown): string {
  if (value === undefined || value === null || value === '') {
    return 'Not entered';
  }

  if (typeof value === 'string') return value;

  return JSON.stringify(value, null, 2) ?? 'Not entered';
}

function fieldLabel5697L(value: string): string {
  return value.replaceAll('_', ' ');
}

export default function DraftHistory5697L({
  projectId,
  load,
}: {
  projectId: string;
  load: (id: string) => Promise<DraftHistoryResponse5697L>;
}) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] =
    useState<DraftHistoryResponse5697L | null>(null);
  const [error, setError] = useState('');

  async function toggle() {
    if (open) {
      setOpen(false);
      return;
    }

    setOpen(true);
    setLoading(true);
    setError('');

    try {
      const response = await load(projectId);

      if (response.project_id !== projectId) {
        throw new Error('Draft history project does not match.');
      }

      setHistory(response);
    } catch (caught) {
      setHistory(null);
      setError(
        caught instanceof Error
          ? caught.message
          : 'Unable to load draft history.'
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ margin: '14px 0 22px' }}>
      <button
        type="button"
        className="quiet"
        aria-expanded={open}
        onClick={() => { void toggle(); }}
      >
        {open ? 'Hide draft history' : 'Draft history'}
      </button>

      {open && (
        <section
          aria-label="Draft save history"
          style={{
            marginTop: 12,
            padding: 16,
            border: '1px solid #D7E3E7',
            borderRadius: 8,
          }}
        >
          <h3>Draft Save History</h3>
          <p className="muted">
            Saved changes within an MSR version.
            This history is read-only and does not replace
            formal Version history.
          </p>

          {loading && <p role="status">Loading draft history...</p>}

          {error && <p role="alert" className="error">{error}</p>}

          {!loading && !error && history && (
            <>
              {history.entries.length === 0 && (
                <p>No draft saves are recorded for this project.</p>
              )}

              {history.entries.map(entry => {
                const changes = Object.entries(
                  entry.changed_fields ?? {}
                );

                const savedAt = new Date(entry.saved_at)
                  .toLocaleString('en-US', {
                    dateStyle: 'medium',
                    timeStyle: 'short',
                    timeZone: 'America/New_York',
                  });

                return (
                  <details
                    key={entry.id}
                    style={{
                      borderTop: '1px solid #D7E3E7',
                      padding: '12px 0',
                    }}
                  >
                    <summary style={{ cursor: 'pointer' }}>
                      <strong>{savedAt} ET</strong>
                      {' ? '}
                      {entry.actor_name}
                      {' ? Version '}
                      {entry.version ?? '?'}
                      .0
                      {' ? Save '}
                      {entry.edit_sequence ?? '?'}
                      {' ? '}
                      {entry.has_explicit_comparison
                        ? `${changes.length} changed field(s)`
                        : 'Saved snapshot'}
                    </summary>

                    {entry.has_explicit_comparison ? (
                      changes.length > 0 ? (
                        <div style={{ marginTop: 12 }}>
                          {changes.map(([field, change]) => (
                            <div
                              key={field}
                              style={{
                                borderBottom: '1px solid #D7E3E7',
                                padding: '8px 0',
                              }}
                            >
                              <strong>{fieldLabel5697L(field)}</strong>
                              <p style={{ whiteSpace: 'pre-wrap' }}>
                                <strong>Before: </strong>
                                {displayValue5697L(change.before)}
                              </p>
                              <p style={{ whiteSpace: 'pre-wrap' }}>
                                <strong>After: </strong>
                                {displayValue5697L(change.after)}
                              </p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p>No field values changed in this save.</p>
                      )
                    ) : (
                      <p className="muted">
                        An earlier save is available.
                        A separate before-and-after comparison
                        was not recorded for this entry.
                      </p>
                    )}

                    <details style={{ marginTop: 12 }}>
                      <summary>View saved snapshot</summary>
                      <pre style={{
                        whiteSpace: 'pre-wrap',
                        overflowWrap: 'anywhere',
                        maxHeight: 400,
                        overflowY: 'auto',
                      }}>
                        {JSON.stringify(entry.snapshot, null, 2)}
                      </pre>
                    </details>
                  </details>
                );
              })}

              {history.more_available && (
                <p className="muted">
                  Showing the latest {history.limit} saves.
                  Additional history is retained but not yet
                  available through this screen.
                </p>
              )}
            </>
          )}
        </section>
      )}
    </div>
  );
}
