import { useEffect, useState } from 'react';

type Product = {
  id: string;
  brand: string;
  residential_system_type: string;
  model_number: string;
  description: string;
  revision: number;
  is_active: boolean;
};
type Details = Pick<Product,
  'brand' | 'residential_system_type' | 'model_number' | 'description'>;
type API = <T>(path: string, method?: string, data?: unknown) => Promise<T>;

const empty: Details = {
  brand: '', residential_system_type: '',
  model_number: '', description: '',
};

export function ProductCatalogManagement4542({
  api, onBack,
}: {
  api: API;
  onBack: () => void;
}) {
  const [rows, setRows] = useState<Product[]>([]);
  const [filter, setFilter] = useState('');
  const [details, setDetails] = useState<Details>(empty);
  const [editing, setEditing] = useState<Product | null>(null);
  const [removing, setRemoving] = useState<Product | null>(null);
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  async function load() {
    const products = await api<Product[]>('development-equipment-management/');
    setRows(products);
  }

  useEffect(() => {
    let cancelled = false;
    void api<Product[]>('development-equipment-management/')
      .then(products => { if (!cancelled) setRows(products); })
      .catch(() => {
        if (!cancelled) setError(
          'Catalog unavailable. The upgraded development database has not been activated.'
        );
      });
    return () => { cancelled = true; };
  }, [api]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await action();
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Catalog action failed.');
    } finally {
      setBusy(false);
    }
  }

  function change(key: keyof Details, value: string) {
    setDetails(current => ({ ...current, [key]: value }));
  }

  function startRevision(product: Product) {
    setEditing(product);
    setRemoving(null);
    setDetails({
      brand: product.brand,
      residential_system_type: product.residential_system_type,
      model_number: product.model_number,
      description: product.description,
    });
  }

  const brands = Array.from(new Set(rows.map(row => row.brand))).sort();
  const visible = rows.filter(row => !filter || row.brand === filter);

  return <section aria-label="Manage product catalog">
    <h2>Product Catalog Management</h2>
    <p className="muted">
      Sales and Installation Managers can add equipment, revise descriptions,
      and deactivate products. Previous versions remain in the audit history.
      Approved MSRs and documents are never rewritten by catalog changes.
    </p>
    <button type="button" className="quiet" onClick={onBack}>
      Return to Customers &amp; Projects
    </button>
    {error && <p role="alert" className="error">{error}</p>}
    {message && <p role="status">{message}</p>}

    <div className="grid">
      <label>Manufacturer
        <select value={filter} onChange={event => setFilter(event.target.value)}>
          <option value="">All manufacturers</option>
          {brands.map(brand => <option key={brand} value={brand}>{brand}</option>)}
        </select>
      </label>
    </div>

    <h3>{editing ? 'Revise Product Description' : 'Add Product'}</h3>
    <form onSubmit={event => {
      event.preventDefault();
      void run(async () => {
        if (editing) {
          await api(
            `development-equipment-management/${editing.id}/`,
            'PATCH', details,
          );
          setMessage('Product revision recorded.');
        } else {
          await api('development-equipment-management/', 'POST', details);
          setMessage('Product added to catalog.');
        }
        setEditing(null);
        setDetails(empty);
      });
    }}>
      <fieldset disabled={busy}>
        <div className="grid">
          {(['brand', 'residential_system_type', 'model_number',
            'description'] as const).map(key =>
            <label key={key}>
              {key.replaceAll('_', ' ')}
              <input
                required
                maxLength={key === 'description' ? 1000
                  : key === 'residential_system_type' ? 200 : 120}
                readOnly={!!editing && key !== 'description'}
                value={details[key]}
                onChange={event => change(key, event.target.value)}
              />
            </label>
          )}
        </div>
        <button type="submit" disabled={busy}>
          {editing ? 'Save New Description Revision' : 'Add Product'}
        </button>
        {editing && <button type="button" className="quiet"
          onClick={() => { setEditing(null); setDetails(empty); }}>
          Cancel Revision
        </button>}
      </fieldset>
    </form>

    <h3>Products ({visible.length})</h3>
    {visible.length === 0 && <p className="muted">
      No products to display. Add a new product using the form above.
    </p>}
    {visible.map(product =>
      <div key={product.id} className="line">
        <div>
          <strong>{product.brand} — {product.model_number}</strong>
          <p>{product.residential_system_type} — {product.description}</p>
          <small>
            Revision {product.revision} |
            {product.is_active ? ' Active' : ' Inactive'}
          </small>
        </div>
        {product.is_active && <>
          <button type="button" className="quiet" disabled={busy}
            onClick={() => startRevision(product)}>Edit</button>
          <button type="button" className="quiet" disabled={busy}
            onClick={() => {
              setRemoving(product);
              setReason('');
              setEditing(null);
            }}>Deactivate</button>
        </>}
      </div>
    )}

    {removing && <form onSubmit={event => {
      event.preventDefault();
      void run(async () => {
        await api(
          `development-equipment-management/${removing.id}/`,
          'DELETE', {reason},
        );
        setRemoving(null);
        setReason('');
        setMessage('Product deactivated; historical records retained.');
      });
    }}>
      <h3>Deactivate {removing.brand} — {removing.model_number}</h3>
      <p>Deactivation removes this version from new equipment selections.
        It does not delete historical records.</p>
      <label>Reason for deactivation
        <input required minLength={10} maxLength={1000}
          value={reason}
          onChange={event => setReason(event.target.value)}/>
      </label>
      <button type="submit" disabled={busy || reason.trim().length < 10}>
        Confirm Deactivation
      </button>
      <button type="button" className="quiet"
        onClick={() => setRemoving(null)}>Cancel</button>
    </form>}
  </section>;
}
