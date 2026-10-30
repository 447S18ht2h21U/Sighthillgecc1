import React, { useEffect, useState } from 'react';

type Engagement = {
  id: string;
  engagement_code: string;
  role_description: string;
  start_date: string | null;
  end_date: string | null;
  status: string;
};

type Contractor = {
  id: string;
  contractor_number: string;
  legal_name: string;
  engagements: Engagement[];
};

type DirectoryResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: Contractor[];
};

type Props = {
  api: <T>(path: string, method?: string, data?: unknown) => Promise<T>;
  onBack: () => void;
  returnLabel?: string;
};

function formatDate(value: string | null): string {
  if (!value) return 'Not recorded';
  return value;
}

function statusLabel(status: string): string {
  return status.replaceAll('_', ' ').toLowerCase();
}

export function ContractorDirectory({ api, onBack, returnLabel = 'Return to Customers & Projects' }: Props) {
  const [contractors, setContractors] = useState<Contractor[]>([]);
  const [search, setSearch] = useState('');
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError('');

      try {
        const response = await api<DirectoryResponse>(
          `contractors/?page=${page}`
        );

        if (cancelled) return;

        setContractors(response.results);
        setCount(response.count);
        setHasNext(Boolean(response.next));
      } catch {
        if (cancelled) return;

        setContractors([]);
        setCount(0);
        setHasNext(false);
        setError(
          'The Contractor Directory could not be opened. ' +
          'Check your access or try again.'
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [api, page]);

  return (
    <section aria-label="Contractor Directory">

      <div className="veridian-guide-banner veridian-guide-banner--info">
        <strong>How to use this directory</strong>
        <p>
          Find a contractor by their name or contractor number.
          Review each service period and its current status.
          This screen does not show private documents or payments.
        </p>
      </div>

      {loading && <p role="status">Loading contractor records...</p>}

      {error && <p role="alert" className="error">{error}</p>}

      {!loading && !error && (
        <>
          <p className="muted">
            {count} contractor{count === 1 ? '' : 's'} recorded
          </p>

          <label>
            Search this page by contractor name or number
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Enter a name or contractor number"
            />
          </label>

          {contractors.length === 0 && (
            <p>No contractor records are available.</p>
          )}

          {contractors.length > 0 && contractors.filter((contractor) =>
            `${contractor.legal_name} ${contractor.contractor_number}`
              .toLowerCase()
              .includes(search.trim().toLowerCase())
          ).length === 0 && (
            <p>No contractors on this page match your search.</p>
          )}

          {contractors.filter((contractor) =>
            `${contractor.legal_name} ${contractor.contractor_number}`
              .toLowerCase()
              .includes(search.trim().toLowerCase())
          ).map((contractor) => (
            <article key={contractor.id} className="card">
              <h3>{contractor.legal_name}</h3>
              <p>
                <strong>Contractor number:</strong>{' '}
                {contractor.contractor_number}
              </p>

              <h4>Engagement history</h4>

              {contractor.engagements.length === 0 ? (
                <p>No engagements recorded.</p>
              ) : (
                <ul>
                  {contractor.engagements.map((engagement) => (
                    <li key={engagement.id}>
                      <strong>{engagement.engagement_code}</strong>
                      {' — '}
                      {engagement.role_description}
                      {' — '}
                      {statusLabel(engagement.status)}
                      <div className="muted">
                        Start: {formatDate(engagement.start_date)}
                        {' | '}
                        End: {formatDate(engagement.end_date)}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </article>
          ))}

          <div className="veridian-navigation-row">
            <button
              className="quiet"
              type="button"
              disabled={loading || page <= 1}
              onClick={() => setPage((value) => value - 1)}
            >
              Previous page
            </button>

            <span>Page {page}</span>

            <button
              className="quiet"
              type="button"
              disabled={loading || !hasNext}
              onClick={() => setPage((value) => value + 1)}
            >
              Next page
            </button>
          </div>
        </>
      )}
    </section>
  );
}