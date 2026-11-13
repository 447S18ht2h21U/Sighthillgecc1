import { useEffect, useState } from 'react';

type Catalog = {
  id: string;
  name: string;
  description: string;
  is_active: boolean;
};

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

type API = <T>(
  path: string, method?: string, data?: unknown
) => Promise<T>;

const endpoint = 'development-product-catalogs/';
const ruudImportPath =
  'development-product-catalogs/import-ruud-2026/';
const bulkCsvPath = 'development-product-catalogs/bulk-csv/';

type BulkReadiness = {
  available: boolean;
  import_available: boolean;
  max_bytes: number;
  max_rows: number;
  required_columns: string[];
  reason: string;
};

type BulkPreview = {
  count: number;
  brands: string[];
  rows: Details[];
  confirmation: string;
  csvText: string;
  name: string;
  description: string;
};

type RuudReadiness = {
  available: boolean;
  catalog: string;
  system_count: number;
  persistent_activation: boolean;
  reason: string;
};

type RuudImportResult = {
  catalog_id: string;
  catalog_name: string;
  added: number;
  total: number;
  status: 'IMPORTED' | 'ALREADY_PRESENT';
  persistent_activation: boolean;
};
const emptyProduct: Details = {
  brand: '',
  residential_system_type: '',
  model_number: '',
  description: '',
};

export function NamedProductCatalog4547({api}: {api: API}) {
  const [catalogs, setCatalogs] = useState<Catalog[]>([]);
  const [catalogId, setCatalogId] = useState('');
  const [products, setProducts] = useState<Product[]>([]);
  const [brandFilter, setBrandFilter] = useState('');
  const [newName, setNewName] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [creatingCatalog, setCreatingCatalog] = useState(false);
  const [details, setDetails] = useState<Details>(emptyProduct);
  const [editing, setEditing] = useState<Product | null>(null);
  const [deactivating, setDeactivating] = useState<
    {kind: 'product' | 'catalog'; id: string; label: string} | null
  >(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [actionFeedback, setActionFeedback] = useState<{
    scope: string;
    status: 'working' | 'success' | 'error';
    message: string;
  } | null>(null);
  const [ruudReady, setRuudReady] =
    useState<RuudReadiness | null>(null);
  const [ruudReadinessError, setRuudReadinessError] =
    useState('');

  const [bulkReady, setBulkReady] = useState<BulkReadiness | null>(null);
  const [bulkReadinessError, setBulkReadinessError] = useState('');
  const [bulkFileName, setBulkFileName] = useState('');
  const [bulkCsv, setBulkCsv] = useState('');
  const [bulkName, setBulkName] = useState('');
  const [bulkDescription, setBulkDescription] = useState('');
  const [bulkPreview, setBulkPreview] = useState<BulkPreview | null>(null);

  const selected = catalogs.find(catalog => catalog.id === catalogId);
  const brands = Array.from(
    new Set(products.map(product => product.brand))
  ).sort();
  const visible = products.filter(
    product => !brandFilter || product.brand === brandFilter
  );

  useEffect(() => {
    let cancelled = false;
    void api<RuudReadiness>(ruudImportPath).then(result => {
      if (!cancelled) setRuudReady(result);
    }).catch(() => {
      if (!cancelled) {
        setRuudReadinessError(
          'Ruud import readiness could not be verified.'
        );
      }
    });
    return () => { cancelled = true; };
  }, [api]);

  useEffect(() => {
    let cancelled = false;
    void api<BulkReadiness>(bulkCsvPath).then(value => {
      if (!cancelled) setBulkReady(value);
    }).catch(() => {
      if (!cancelled) {
        setBulkReady(null);
        setBulkReadinessError(
          'CSV import readiness could not be verified.'
        );
      }
    });
    return () => { cancelled = true; };
  }, [api]);

  function bulkPayload(
    action: 'preview' | 'import',
    csvText: string,
    name: string,
    description: string,
    confirmation: string | null,
  ) {
    return {
      action,
      name,
      description,
      catalog_id: null,
      csv_text: csvText,
      confirmation,
    };
  }

  async function selectBulkFile(file?: File) {
    setBulkPreview(null);
    setBulkCsv('');
    setBulkFileName('');
    setError('');
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.csv')) {
      setError('Select a CSV file with the four required columns.');
      return;
    }

    if (file.size === 0 || file.size > (bulkReady?.max_bytes ?? 2000000)) {
      setError('CSV file must contain 1 to 2,000,000 bytes.');
      return;
    }

    try {
      const text = await file.text();
      setBulkCsv(text);
      setBulkFileName(file.name);
    } catch {
      setError('The selected CSV file could not be read.');
    }
  }

  async function refreshCatalogs(preferredId?: string) {
    const next = await api<Catalog[]>(endpoint);
    setCatalogs(next);
    setCatalogId(current => {
      if (preferredId && next.some(c => c.id === preferredId)) {
        return preferredId;
      }
      if (next.some(c => c.id === current)) return current;
      return next.find(c => c.is_active)?.id ?? next[0]?.id ?? '';
    });
  }

  async function refreshProducts(id: string) {
    if (!id) {
      setProducts([]);
      return;
    }
    const next = await api<Product[]>(
      `${endpoint}${id}/products/`
    );
    setProducts(next);
  }

  useEffect(() => {
    let cancelled = false;
    void api<Catalog[]>(endpoint).then(next => {
      if (cancelled) return;
      setCatalogs(next);
      setCatalogId(
        next.find(c => c.is_active)?.id ?? next[0]?.id ?? ''
      );
    }).catch(cause => {
      if (!cancelled) {
        setError(cause instanceof Error
          ? cause.message
          : 'Named catalogs are not available.');
      }
    });
    return () => { cancelled = true; };
  }, [api]);

  useEffect(() => {
    let cancelled = false;
    if (!catalogId) {
      setProducts([]);
      return;
    }
    setProducts([]);
    setBrandFilter('');
    void api<Product[]>(
      `${endpoint}${catalogId}/products/`
    ).then(next => {
      if (!cancelled) setProducts(next);
    }).catch(cause => {
      if (!cancelled) {
        setError(cause instanceof Error
          ? cause.message
          : 'Unable to load catalog products.');
      }
    });
    return () => { cancelled = true; };
  }, [api, catalogId]);

  async function run(
    action: () => Promise<void>,
    scope = 'general',
    successMessage = 'Action completed successfully.',
  ) {
    if (busy) return;
    setBusy(true);
    setError('');
    setNotice('');
    setActionFeedback(scope === 'general' ? null : {
      scope,
      status: 'working',
      message: 'Processing...',
    });
    try {
      await action();
      if (scope !== 'general') {
        setActionFeedback({
          scope,
          status: 'success',
          message: successMessage,
        });
      }
    } catch (cause) {
      const message = cause instanceof Error
        ? cause.message
        : 'Catalog operation failed.';
      setError(message);
      if (scope !== 'general') {
        setActionFeedback({
          scope,
          status: 'error',
          message: `Unable to complete action: ${message}`,
        });
      }
    } finally {
      setBusy(false);
    }
  }

  function updateField(key: keyof Details, value: string) {
    setDetails(current => ({...current, [key]: value}));
  }

  function beginRevision(product: Product) {
    setEditing(product);
    setDeactivating(null);
    setDetails({
      brand: product.brand,
      residential_system_type: product.residential_system_type,
      model_number: product.model_number,
      description: product.description,
    });
  }

  function clearEditor() {
    setEditing(null);
    setDetails(emptyProduct);
  }

  function beginDeactivation(
    kind: 'product' | 'catalog',
    id: string,
    label: string,
  ) {
    clearEditor();
    setReason('');
    setDeactivating({kind, id, label});
  }

  function feedbackFor(scope: string) {
    if (actionFeedback?.scope !== scope) return null;
    return <span
      role={actionFeedback.status === 'error' ? 'alert' : 'status'}
      aria-live="polite"
      className={`catalog-action-feedback ${actionFeedback.status}`}
    >
      {actionFeedback.message}
    </span>;
  }

  const deactivationForm = (
    kind: 'catalog' | 'product', id: string,
  ) => deactivating?.kind === kind && deactivating.id === id
    ? <form
        className="catalog-inline-confirmation"
        onSubmit={event => {
      event.preventDefault();
      void run(async () => {
        if (deactivating.kind === 'catalog') {
          await api(
            `${endpoint}${deactivating.id}/`,
            'DELETE', {reason},
          );
          await refreshCatalogs();
          setNotice('Catalog deactivated. Historical records retained.');
        } else {
          await api(
            `${endpoint}${catalogId}/products/${deactivating.id}/`,
            'DELETE', {reason},
          );
          await refreshProducts(catalogId);
          setNotice('Product deactivated. Historical records retained.');
        }
        setDeactivating(null);
        setReason('');
      },
        deactivating.kind === 'catalog'
          ? `catalog:${deactivating.id}`
          : `product:${deactivating.id}`,
        deactivating.kind === 'catalog'
          ? 'Catalog deactivated successfully.'
          : 'Product deactivated successfully.',
      );
    }}>
      <h3>
        Deactivate {deactivating.kind === 'catalog'
          ? 'Catalog' : 'Product'}: {deactivating.label}
      </h3>
      <p className="muted">
        Deactivation prevents future selection. Previous revisions
        and customer document snapshots are not deleted.
      </p>
      <label>
        Reason for Deactivation
        <textarea
          required rows={3} minLength={10} maxLength={1000}
          value={reason}
          onChange={event => setReason(event.target.value)}
        />
      </label>
      <button type="submit" className="catalog-confirm-primary"
        disabled={busy || reason.trim().length < 10}
      >
        Confirm Deactivation
      </button>
      <button type="button" className="quiet catalog-cancel"
        onClick={() => setDeactivating(null)}
      >
        Cancel
      </button>
    </form> : null;

  return <section aria-label="Named product catalogs">
    <h2>Product Catalog Management</h2>
    <p className="muted">
      Create separate equipment catalogs and manage their products.
      Sales Managers and Installation Managers can make changes.
      Historical product revisions and approved MSR snapshots remain
      preserved.
    </p>

    {error && <p role="alert" className="error">{error}</p>}
    {notice && <p role="status">{notice}</p>}

    <section aria-label="Ruud catalog import">
      <h3>Ruud Residential Systems — 2026</h3>
      <p className="muted">
        15 complete air-conditioning and furnace configurations,
        including AHRI references, outdoor models, coils,
        furnaces, cooling capacities and SEER2 ratings.
        Existing Goodman records are not changed.
      </p>
      <p className="muted" role="status">
        {ruudReadinessError ||
          ruudReady?.reason ||
          'Checking protected import availability...'}
      </p>
      <button
        type="button"
        disabled={busy || !ruudReady?.available}
        onClick={() => void run(async () => {
          const result = await api<RuudImportResult>(
            ruudImportPath, 'POST', {}
          );
          await refreshCatalogs(result.catalog_id);
          await refreshProducts(result.catalog_id);
          setNotice(
            result.added === 15
              ? 'All 15 Ruud systems imported with audit history.'
              : 'The 15 Ruud systems are already present.'
          );
        })}
      >
        Import 15 Ruud Systems
      </button>
    </section>

    <section aria-label="Bulk CSV catalog import">
      <h3>Import a Manufacturer Catalog (CSV)</h3>
      <p className="muted">
        Upload a CSV file containing these four columns, in order:
        brand, residential_system_type, model_number, description.
        Review every product before confirming. Maximum 500 products
        per file. Historical catalog records remain protected.
      </p>
      <p className="muted" role="status">
        {bulkReadinessError ||
          bulkReady?.reason ||
          'Checking protected CSV import availability...'}
      </p>
      <fieldset disabled={busy || !bulkReady?.available}>
        <label>
          CSV File
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={event =>
              void selectBulkFile(event.currentTarget.files?.[0])}
          />
        </label>
        {bulkFileName && <p className="muted">
          Selected: {bulkFileName}
        </p>}
        <div className="grid">
          <label>
            New Catalog Name
            <input
              maxLength={120}
              value={bulkName}
              onChange={event => {
                setBulkName(event.target.value);
                setBulkPreview(null);
              }}
              placeholder="Example: Carrier Residential"
            />
          </label>
          <label>
            Catalog Description (optional)
            <input
              maxLength={500}
              value={bulkDescription}
              onChange={event => {
                setBulkDescription(event.target.value);
                setBulkPreview(null);
              }}
            />
          </label>
        </div>
        <button
          type="button"
          disabled={!bulkCsv || !bulkName.trim() || busy}
          onClick={() => void run(async () => {
            setBulkPreview(null);
            const response = await api<{
              count: number;
              brands: string[];
              rows: Details[];
              confirmation: string;
            }>(
              bulkCsvPath,
              'POST',
              bulkPayload(
                'preview', bulkCsv, bulkName,
                bulkDescription, null,
              ),
            );
            setBulkPreview({
              ...response,
              csvText: bulkCsv,
              name: bulkName,
              description: bulkDescription,
            });
            setNotice(
              `${response.count} products validated. Review before importing.`
            );
          })}
        >
          Preview CSV Products
        </button>
      </fieldset>
      {feedbackFor('csv-import')}

      {bulkPreview && bulkReady?.available && (
        <div>
          <h4>Review {bulkPreview.count} Products</h4>
          <p className="muted">
            Catalog: {bulkPreview.name}.
            Manufacturers: {bulkPreview.brands.join(', ')}.
            No records have been imported yet.
          </p>
          <div style={{maxHeight: 280, overflowY: 'auto'}}>
            {bulkPreview.rows.map((item, index) =>
              <div className="line" key={`${index}-${item.model_number}`}>
                <div>
                  <strong>{item.brand} — {item.model_number}</strong>
                  <p>
                    {item.residential_system_type} — {item.description}
                  </p>
                </div>
              </div>
            )}
          </div>
          <p className="muted" role="status">
            {bulkReady.import_available
              ? 'Confirmed import is available in this local development environment.'
              : 'Preview only. Importing into the development database is not yet authorized.'}
          </p>
          <button
            type="button"
            disabled={busy || !bulkReady.import_available}
            onClick={() => void run(async () => {
              const preview = bulkPreview;
              const result = await api<{
                catalog_id: string;
                catalog_name: string;
                added: number;
              }>(
                bulkCsvPath,
                'POST',
                bulkPayload(
                  'import',
                  preview.csvText,
                  preview.name,
                  preview.description,
                  preview.confirmation,
                ),
              );
              await refreshCatalogs(result.catalog_id);
              await refreshProducts(result.catalog_id);
              setBulkPreview(null);
              setBulkCsv('');
              setBulkFileName('');
              setBulkName('');
              setBulkDescription('');
              setNotice(
                `${result.added} products imported into ${result.catalog_name} with audit history.`
              );
            }, 'csv-import', 'Catalog imported successfully.')}
          >
            Confirm Import of {bulkPreview.count} Products
          </button>
          <button
            type="button"
            className="quiet"
            disabled={busy}
            onClick={() => setBulkPreview(null)}
          >
            Cancel Preview
          </button>
        </div>
      )}
    </section>

    <div className="grid">
      <label>
        Product Catalog
        <select
          value={catalogId}
          onChange={event => {
            setCatalogId(event.target.value);
            clearEditor();
            setDeactivating(null);
            setCreatingCatalog(false);
            setNewName('');
            setNewDescription('');
            setError('');
            setNotice('');
          }}
          disabled={busy}
        >
          {catalogs.length === 0 &&
            <option value="">No catalogs created</option>}
          {catalogs.map(catalog =>
            <option key={catalog.id} value={catalog.id}>
              {catalog.name}{catalog.is_active ? '' : ' (Inactive)'}
            </option>
          )}
        </select>
      </label>
      <div>
        <p className="muted">Catalog administration</p>
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            if (creatingCatalog) {
              setNewName('');
              setNewDescription('');
            }
            setCreatingCatalog(current => !current);
            setDeactivating(null);
          }}
        >
          {creatingCatalog ? 'Close Add Catalog' : 'Add Catalog'}
        </button>
      </div>
    </div>

    {creatingCatalog &&
      <form onSubmit={event => {
        event.preventDefault();
        void run(async () => {
          const created = await api<Catalog>(
            endpoint,
            'POST',
            {name: newName, description: newDescription},
          );
          await refreshCatalogs(created.id);
          setNewName('');
          setNewDescription('');
          setCreatingCatalog(false);
          setNotice(`Catalog ${created.name} created.`);
        });
      }}>
        <h3>Create a New Catalog</h3>
        <div className="grid">
          <label>
            Catalog Name
            <input
              required
              maxLength={120}
              value={newName}
              onChange={event => setNewName(event.target.value)}
              placeholder="Example: Goodman Residential"
              disabled={busy}
            />
          </label>
          <label>
            Catalog Description (optional)
            <input
              maxLength={500}
              value={newDescription}
              onChange={event => setNewDescription(event.target.value)}
              disabled={busy}
            />
          </label>
        </div>
        <button type="submit" disabled={busy || !newName.trim()}>
          Save New Catalog
        </button>
      </form>
    }

    {selected &&
      <div>
        <h3>{selected.name}</h3>
        {selected.description && <p>{selected.description}</p>}
        <p className="muted">
          Status: {selected.is_active ? 'Active' : 'Inactive'}
        </p>
        {selected.is_active &&
          <button
            type="button"
            className="quiet"
            disabled={busy}
            onClick={() => beginDeactivation(
              'catalog', selected.id, selected.name
            )}
          >
            Deactivate Catalog
          </button>
        }
        {feedbackFor(`catalog:${selected.id}`)}
        {deactivationForm('catalog', selected.id)}
      </div>
    }

    {selected?.is_active && <>
      <h3>{editing ? 'Edit Product Description' : 'Add Product'}</h3>
      <p className="muted">
        {editing
          ? 'Saving creates a new product revision. The previous description remains in history.'
          : `Products added here will belong to ${selected.name}.`}
      </p>
      <form onSubmit={event => {
        event.preventDefault();
        if (!catalogId) return;
        void run(async () => {
          const productPath =
            `${endpoint}${catalogId}/products/`;

          if (editing) {
            await api(
              `${productPath}${editing.id}/`,
              'PATCH', details,
            );
            setNotice('New product description revision saved.');
          } else {
            await api(productPath, 'POST', details);
            setNotice('Product added to selected catalog.');
          }
          clearEditor();
          await refreshProducts(catalogId);
        });
      }}>
        <fieldset disabled={busy}>
          <div className="grid">
            <label>
              Brand / Manufacturer
              <input required maxLength={120}
                readOnly={!!editing}
                value={details.brand}
                onChange={event =>
                  updateField('brand', event.target.value)}
              />
            </label>
            <label>
              Residential System Type
              <input required maxLength={200}
                readOnly={!!editing}
                value={details.residential_system_type}
                onChange={event =>
                  updateField('residential_system_type', event.target.value)}
              />
            </label>
            <label>
              Model Number
              <input required maxLength={120}
                readOnly={!!editing}
                value={details.model_number}
                onChange={event =>
                  updateField('model_number', event.target.value)}
              />
            </label>
          </div>
          <label>
            Product Description
            <textarea required rows={4} maxLength={1000}
              style={{width: '100%', boxSizing: 'border-box'}}
              value={details.description}
              onChange={event =>
                updateField('description', event.target.value)}
            />
          </label>
          <button type="submit" disabled={busy}>
            {editing ? 'Save Description Revision' : 'Add Product'}
          </button>
          {editing && <button
            type="button" className="quiet"
            onClick={clearEditor}
          >
            Cancel Editing
          </button>}
        </fieldset>
      </form>
    </>}

    <h3>Catalog Products ({visible.length})</h3>
    <label>
      Filter by Manufacturer
      <select
        value={brandFilter}
        onChange={event => setBrandFilter(event.target.value)}
      >
        <option value="">All manufacturers</option>
        {brands.map(brand =>
          <option key={brand} value={brand}>{brand}</option>
        )}
      </select>
    </label>

    {visible.length === 0 &&
      <p className="muted">
        {selected
          ? 'No products in this catalog.'
          : 'Create a catalog to begin adding products.'}
      </p>
    }

    {visible.map(product =>
      <div className="line" key={product.id}>
        <div>
          <strong>
            {product.brand} — {product.model_number}
          </strong>
          <p>
            {product.residential_system_type} — {product.description}
          </p>
          <small>
            Revision {product.revision} |
            {product.is_active ? ' Active' : ' Inactive'}
          </small>
        </div>
        {selected?.is_active && product.is_active && <>
          <button
            type="button" className="quiet"
            disabled={busy}
            onClick={() => beginRevision(product)}
          >
            Edit
          </button>
          <button
            type="button" className="quiet"
            disabled={busy}
            onClick={() => beginDeactivation(
              'product',
              product.id,
              `${product.brand} — ${product.model_number}`,
            )}
          >
            Deactivate
          </button>
        </>}
        {feedbackFor(`product:${product.id}`)}
        {deactivationForm('product', product.id)}
      </div>
    )}


  </section>;
}
