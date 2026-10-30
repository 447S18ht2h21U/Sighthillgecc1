import { useEffect, useState } from 'react';

type API = <T>(
  path: string,
  method?: string,
  data?: unknown
) => Promise<T>;

type MarketingMSR = {
  id: string;
  number: number;
  status: string;
  snapshot: Record<string, unknown>;
  revision_reason: string;
  approved_at: string | null;
};

type Page<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

type Props = {
  api: API;
};

function fieldLabel(key: string): string {
  return key.replaceAll('_', ' ').replace(/\b\w/g, letter =>
    letter.toUpperCase()
  );
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return 'Not recorded';
  }

  if (typeof value === 'string') return value;
  if (typeof value === 'number') return String(value);
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';

  return JSON.stringify(value, null, 2);
}

function customerName(record: MarketingMSR): string {
  const value = record.snapshot.customer;
  return typeof value === 'string' && value.trim()
    ? value
    : 'Customer not recorded';
}

export function MarketingMSRDirectory({ api }: Props) {
  const [page, setPage] = useState(1);
  const [records, setRecords] = useState<MarketingMSR[]>([]);
  const [count, setCount] = useState(0);
  const [next, setNext] = useState(false);
  const [previous, setPrevious] = useState(false);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<MarketingMSR | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError('');
      setRecords([]);
      setSelected(null);

      try {
        const response = await api<Page<MarketingMSR>>(
          `marketing-msrs/?page=${page}`
        );

        if (cancelled) return;

        setRecords(response.results);
        setCount(response.count);
        setNext(Boolean(response.next));
        setPrevious(Boolean(response.previous));
      } catch {
        if (cancelled) return;

        setCount(0);
        setNext(false);
        setPrevious(false);
        setError(
          'Master Sales Records could not be loaded. ' +
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
  }, [api, page, refreshKey]);

  const matching = records.filter(record => {
    const query = search.trim().toLowerCase();

    if (!query) return true;

    return [
      customerName(record),
      record.status,
      String(record.number),
      record.id
    ].some(value => value.toLowerCase().includes(query));
  });

  return (
    <section aria-label="Marketing Master Sales Records">
      <div className="title">
        <div>
          <p className="eyebrow">MARKETING / COMMERCIAL RECORDS</p>
          <h2>Master Sales Records</h2>
          <p className="muted">
            Review records from all Sales Associates.
          </p>
        </div>
        <button
          type="button"
          className="quiet"
          disabled={loading}
          onClick={() => setRefreshKey(value => value + 1)}
        >
          Refresh records
        </button>
      </div>

      <div className="veridian-guide-banner veridian-guide-banner--info">
        <strong>How to use this screen</strong>
        <p>
          Step 1 - Review the records listed on this page.
          Use Next page to see more records.
        </p>
        <p>
          Step 2 - Search the current page by customer, status,
          version number, or record ID.
        </p>
        <p>
          Step 3 - Select View record to read its details.
          You cannot change or approve records here.
        </p>
      </div>

      {loading && (
        <p role="status">Loading Master Sales Records...</p>
      )}

      {error && (
        <p role="alert" className="error">{error}</p>
      )}

      {!loading && !error && (
        <>
          <p role="status" className="muted">
            {count} record{count === 1 ? '' : 's'} available.
            {' '}Page {page}.
          </p>

          <label>
            Search this page
            <input
              type="search"
              value={search}
              maxLength={200}
              onChange={event => setSearch(event.target.value)}
              placeholder="Customer, status, version, or record ID"
            />
          </label>

          {matching.length === 0 && (
            <p>
              {records.length === 0
                ? 'No Master Sales Records are available.'
                : 'No records on this page match your search.'}
            </p>
          )}

          <div className="record-filters">
            {matching.map(record => (
              <section key={record.id}>
                <h3>{customerName(record)}</h3>
                <p className="muted">
                  Version {record.number}.0 ·{' '}
                  {fieldLabel(record.status)}
                </p>
                <button
                  type="button"
                  className="quiet"
                  aria-label={`View record for ${customerName(record)}, version ${record.number}`}
                  onClick={() => setSelected(record)}
                >
                  View record
                </button>
              </section>
            ))}
          </div>

          <div className="actions">
            <button
              type="button"
              className="quiet"
              disabled={!previous}
              onClick={() => setPage(value => Math.max(1, value - 1))}
            >
              Previous page
            </button>
            <button
              type="button"
              className="quiet"
              disabled={!next}
              onClick={() => setPage(value => value + 1)}
            >
              Next page
            </button>
          </div>
        </>
      )}

      {selected && !loading && !error && (
        <article aria-label="Read-only Master Sales Record">
          <div className="title">
            <div>
              <h2>{customerName(selected)}</h2>
              <p className="muted">
                MSR version {selected.number}.0 ·{' '}
                {fieldLabel(selected.status)}
              </p>
            </div>
            <button
              type="button"
              className="quiet"
              onClick={() => setSelected(null)}
            >
              Close record
            </button>
          </div>

          <p className="muted">
            Read-only record. No changes can be made here.
          </p>

          {selected.revision_reason && (
            <p>
              <strong>Revision reason:</strong>{' '}
              {selected.revision_reason}
            </p>
          )}

          <dl>
            {Object.entries(selected.snapshot).map(([key, value]) => (
              <div key={key}>
                <dt><strong>{fieldLabel(key)}</strong></dt>
                <dd>
                  <span style={{ whiteSpace: 'pre-wrap' }}>
                    {displayValue(value)}
                  </span>
                </dd>
              </div>
            ))}
          </dl>
        </article>
      )}
    </section>
  );
}