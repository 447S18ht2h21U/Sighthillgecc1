import { useEffect, useState } from 'react';

type API = <T>(path: string, method?: string, data?: unknown) => Promise<T>;

type Opportunity = {
  id: string;
  code: string;
  location: string;
  state: string;
  sales_status?: string | null;
};

type Page<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export function CustomerOpportunityHistory5036({
  api,
  customerId,
}: {
  api: API;
  customerId: string;
}) {
  const [page, setPage] = useState(1);
  const [history, setHistory] = useState<Page<Opportunity> | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    setPage(1);
  }, [customerId]);

  useEffect(() => {
    let cancelled = false;
    setHistory(null);
    setError('');

    const params = new URLSearchParams({
      customer: customerId,
      page: String(page),
    });

    api<Page<Opportunity>>(`projects/?${params}`)
      .then(data => {
        if (!cancelled) setHistory(data);
      })
      .catch(err => {
        if (!cancelled) setError((err as Error).message);
      });

    return () => {
      cancelled = true;
    };
  }, [api, customerId, page]);

  const label = (value: string) =>
    value.replace(/_/g, ' ').toLowerCase()
      .replace(/\b\w/g, character => character.toUpperCase());

  return (
    <section aria-label="Customer opportunity history">
      <h3>Customer opportunity history</h3>
      <p className="muted">
        Historical opportunities remain available regardless of
        commercial outcome. Project and sales statuses are separate.
      </p>

      {error && <p role="alert">{error}</p>}

      {history ? (
        <>
          <p role="status">{history.count} recorded opportunities</p>

          {history.count === 0 && (
            <p>No projects are available in this customer history.</p>
          )}

          <ul className="customer-record-list">
            {history.results.map(project => (
              <li key={project.id}>
                <strong>{project.code}</strong>
                <p>{project.location}</p>
                <p>Project: {label(project.state)}</p>
                <p>
                  Sales: {project.sales_status
                    ? label(project.sales_status)
                    : 'Not available'}
                </p>
              </li>
            ))}
          </ul>

          <div className="actions">
            <button
              type="button"
              className="quiet"
              disabled={!history.previous}
              onClick={() => setPage(value => Math.max(1, value - 1))}
            >
              Previous opportunities
            </button>
            <span>Page {page}</span>
            <button
              type="button"
              className="quiet"
              disabled={!history.next}
              onClick={() => setPage(value => value + 1)}
            >
              Next opportunities
            </button>
          </div>
        </>
      ) : (
        !error && <p>Loading opportunity history...</p>
      )}
    </section>
  );
}
