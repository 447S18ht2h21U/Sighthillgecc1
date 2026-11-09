import { useEffect, useState } from 'react';

type API = <T>(
  path: string,
  method?: string,
  data?: unknown,
) => Promise<T>;

type Source = {
  source: 'CURRENT_APPROVED_MSR';
  read_only: true;
  document_generation_authorized: false;
  project_id: string;
  project_code: string;
  msr_id: string;
  msr_number: number;
  msr_status: string;
  fields: Record<string, string>;
  equipment_count: number;
  pending_revision_excluded: true;
};

const displayed = [
  ['customer', 'Customer'],
  ['project_location', 'Installation address'],
  ['project_city', 'City'],
  ['project_state', 'State'],
  ['project_zip', 'ZIP'],
  ['financing_type', 'Financing classification'],
  ['base_price', 'Base price'],
  ['discount', 'Discount'],
  ['tax', 'Tax'],
  ['total_price', 'Total price'],
] as const;

export function ApprovedMSRSource4530({
  api,
  projectId,
}: {
  api: API;
  projectId: string;
}) {
  const [source, setSource] = useState<Source | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setSource(null);
    setError('');
    setLoading(true);
    void api<Source>(
      `development-approved-msr-source/${projectId}/`
    ).then(result => {
      if (cancelled) return;
      if (
        result.source !== 'CURRENT_APPROVED_MSR' ||
        result.read_only !== true ||
        result.document_generation_authorized !== false ||
        result.pending_revision_excluded !== true ||
        result.project_id !== projectId
      ) {
        throw new Error('Unexpected approved-MSR source response.');
      }
      setSource(result);
    }).catch(() => {
      if (!cancelled) setError(
        'Approved MSR source is unavailable or access is denied.'
      );
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [api, projectId]);

  if (!import.meta.env.DEV) return null;

  return (
    <details className="veridian-guide-banner veridian-guide-banner--info">
      <summary>Document Source — Approved MSR (development inspection)</summary>
      <p>
        Read-only values from this project's current approved MSR.
        Unsaved and pending revisions are excluded.
        This is not a customer document, signing approval or release.
      </p>
      {loading && <p role="status">Checking approved MSR...</p>}
      {error && <p role="alert">{error}</p>}
      {source && (
        <>
          <p>
            <strong>Project:</strong> {source.project_code}
            {' · '}
            <strong>Approved MSR:</strong> Version {source.msr_number}.0
          </p>
          <dl>
            {displayed.map(([key, label]) => (
              <div key={key}>
                <dt>{label}</dt>
                <dd>{source.fields[key] || 'Not recorded'}</dd>
              </div>
            ))}
            <div>
              <dt>Equipment rows</dt>
              <dd>{source.equipment_count}</dd>
            </div>
          </dl>
          <p className="muted">
            Data source verified. Actual PDF generation, document
            retention, signing and delivery remain separate controls.
          </p>
        </>
      )}
    </details>
  );
}
