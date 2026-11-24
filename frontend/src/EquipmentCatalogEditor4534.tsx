import { useEffect, useState } from 'react';

export type LegacyEquipmentLine = {
  description: string;
  quantity: string;
};

export type CatalogEquipmentLine = {
  brand: string;
  residential_system_type: string;
  model_number: string;
  description: string;
  quantity: number;
  category_of_work: string;
  catalog_id?: string;
  equipment_id?: string;
};

export type EquipmentLine = LegacyEquipmentLine | CatalogEquipmentLine;

type CatalogItem = {
  id: string;
  brand: string;
  residential_system_type: string;
  model_number: string;
  description: string;
};

type NamedCatalog = {
  id: string;
  name: string;
  products: CatalogItem[];
};

type API = <T>(
  path: string,
  method?: string,
  data?: unknown,
) => Promise<T>;

const categories = [
  'New installation',
  'Replacing existing equipment',
  'Service',
  'Repair',
];

function isCatalogLine(line: EquipmentLine): line is CatalogEquipmentLine {
  return 'model_number' in line;
}

export function EquipmentCatalogEditor4534({
  items,
  onChange,
  api,
  primaryCategory,
}: {
  items: EquipmentLine[];
  onChange: (items: EquipmentLine[]) => void;
  api: API;
  primaryCategory: string;
}) {
  const [catalogs, setCatalogs] = useState<NamedCatalog[]>([]);
  const [catalogId, setCatalogId] = useState('');
  const [selectedId, setSelectedId] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    void api<NamedCatalog[]>('development-msr-named-catalogs/')
      .then(result => {
        if (cancelled) return;
        setCatalogs(result);
        setCatalogId(result[0]?.id ?? '');
        setSelectedId('');
        setError(result.length
          ? ''
          : 'No active named product catalogs are available.');
      })
      .catch(() => {
        if (cancelled) return;
        setCatalogs([]);
        setCatalogId('');
        setSelectedId('');
        setError(
          'Named product catalogs are unavailable. Ask your manager to check the development catalog setup.'
        );
      });
    return () => { cancelled = true; };
  }, [api]);

  const currentCatalog = catalogs.find(row => row.id === catalogId);
  const products = currentCatalog?.products ?? [];

  function replace(index: number, updated: EquipmentLine) {
    onChange(items.map((line, i) => i === index ? updated : line));
  }

  function add() {
    if (items.length >= 100 || !categories.includes(primaryCategory)) return;
    const selected = products.find(row => row.id === selectedId);
    if (!selected) return;

    onChange([...items, {
      catalog_id: catalogId,
      equipment_id: selected.id,
      brand: selected.brand,
      residential_system_type: selected.residential_system_type,
      model_number: selected.model_number,
      description: selected.description,
      quantity: 1,
      category_of_work: primaryCategory,
    }]);
    setSelectedId('');
  }

  return (
    <section aria-label="MSR equipment catalog selection">
      <h3>Equipment</h3>
      <p className="muted">
        Check each equipment item below. Choose the work needed
        and enter the quantity.
      </p>

      {error && <p role="status">{error}</p>}

      {items.map((line, index) => (
        <div className="line" key={index}
          style={{
            display:'grid',
            gridTemplateColumns:'110px max-content minmax(0,1fr)',
            gap:'10px 14px',
            alignItems:'end',
            width:'100%',
            boxSizing:'border-box',
            border:'1px solid #D7E3E7',
            borderRadius:8,
            padding:'12px 16px',
            marginBottom:12
          }}>
          <h4 style={{
            gridColumn:'1 / -1',
            fontSize:'1.1rem',
            margin:0,
            color:'#142B3B'
          }}>
            Equipment {index + 1}
          </h4>
          {isCatalogLine(line) ? (
            <>
              <p style={{
                gridColumn:'1 / -1',
                margin:'0 0 2px',
                lineHeight:1.5,
                overflowWrap:'anywhere'
              }}>
                <strong>{line.brand} — {line.model_number}</strong>
                {' — '}{line.residential_system_type}
                {' — '}{line.description}
              </p>
              {line.category_of_work !== primaryCategory &&
                <p className="muted" style={{
                  gridColumn:'1 / -1',margin:0
                }}>
                  Individual category: {line.category_of_work}
                </p>}
              <div className="msr-equipment-category-override"
                style={{
                  gridColumn:'1 / -1',
                  order:3,
                  borderTop:'1px solid #D7E3E7',
                  paddingTop:12,
                  margin:'4px 0 0',
                  minWidth:0
                }}>
                <strong>Work required for this equipment</strong>
                <p className="muted">
                  Choose one. It can differ from the overall Scope of Work.
                </p>
                {line.category_of_work === 'Service & maintenance' &&
                  <p className="muted">
                    Historical category: Service &amp; maintenance
                  </p>}
                <div style={{display:'flex',flexWrap:'wrap',gap:14}}>
                  {categories.map(value => (
                    <label key={value}
                      style={{display:'flex',alignItems:'center',gap:6,width:'auto'}}>
                      <input
                        type="radio"
                        name={`equipment-category-${index}`}
                        style={{width:17,height:17,minWidth:17,margin:0}}
                        checked={line.category_of_work === value}
                        onChange={() => replace(index, {
                          ...line,
                          category_of_work:value,
                        })}
                      />
                      {value === 'Replacing existing equipment'
                        ? 'Replacing Equipment'
                        : value === 'New installation'
                          ? 'New Installation'
                          : value}
                    </label>
                  ))}
                </div>
              </div>
              <label style={{
                width:110,
                maxWidth:'100%',
                gridColumn:'1',
                order:1,
                margin:0
              }}>
                Quantity
                <input type="number" min="1" max="999" step="1"
                  style={{width:'100%',boxSizing:'border-box'}}
                  value={line.quantity}
                  onChange={event => {
                    const value = Number(event.target.value);
                    if (
                      Number.isInteger(value)
                      && value >= 1
                      && value <= 999
                    ) {
                      replace(index, {...line, quantity: value});
                    }
                  }}/>
              </label>
            </>
          ) : (
            <p style={{gridColumn:"1 / -1",margin:0,overflowWrap:"anywhere"}}>
              Historical equipment entry: {line.description}
              {' — Quantity: '}{line.quantity}
            </p>
          )}
          <button type="button" className="quiet"
            style={{
              alignSelf:'end',
              justifySelf:'start',
              gridColumn:'2',
              order:2,
              whiteSpace:'nowrap'
            }}
            onClick={() => onChange(items.filter((_, i) => i !== index))}>
            Remove equipment
          </button>
        </div>
      ))}

      <div style={{
        borderTop:'1px solid #D7E3E7',
        paddingTop:16,
        marginTop:12
      }}>
      <h4 style={{fontSize:'1.1rem',margin:'0 0 12px'}}>
        Add another equipment item
      </h4>
      <label>
        Product Catalog
        <select
          aria-label="Product Catalog for MSR equipment"
          value={catalogId}
          onChange={event => {
            setCatalogId(event.target.value);
            setSelectedId('');
          }}
        >
          {catalogs.length === 0 &&
            <option value="">No active catalogs</option>}
          {catalogs.map(row => (
            <option value={row.id} key={row.id}>{row.name}</option>
          ))}
        </select>
      </label>

      <label>
        Add Equipment from Selected Catalog
        <select
          value={selectedId}
          onChange={event => setSelectedId(event.target.value)}
        >
          <option value="">Choose active equipment</option>
          {products.map(row => (
            <option key={row.id} value={row.id}>
              {row.brand} | {row.residential_system_type}
              {' | '}{row.model_number} | {row.description}
            </option>
          ))}
        </select>
      </label>

      {currentCatalog && products.length === 0 &&
        <p className="muted">
          This catalog contains no active equipment.
        </p>
      }

      <button type="button" className="msr-add-equipment-primary"
        disabled={!selectedId || !primaryCategory || items.length >= 100}
        onClick={add}>
        Add Selected Equipment
      </button>

      <p className="muted">
        Choose an active product and select Add Selected Equipment.
        Saved equipment details are retained with the record.
      </p>
      </div>
    </section>
  );
}
