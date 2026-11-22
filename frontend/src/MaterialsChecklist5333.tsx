import { useState } from 'react';

export type MaterialLine = {
  description: string;
  quantity: string;
};

const choices = [
  { name: 'Ductwork', unit: 'linear feet' },
  { name: 'Refrigerant', unit: 'lb' },
  { name: 'Electrical wiring', unit: 'linear feet' },
  { name: 'Permit', unit: 'each' },
  { name: 'Circuit breaker', unit: 'each' },
  { name: 'Disconnect / lockout', unit: 'each' },
  { name: 'Insulation', unit: 'square feet' },
  { name: 'Metal tape', unit: 'rolls' },
  { name: 'Filters', unit: 'each' },
] as const;

function matchingIndex(items: MaterialLine[], name: string, unit: string) {
  const canonical = `${name} (${unit})`.toLowerCase();
  return items.findIndex(item => {
    const description = item.description.trim().toLowerCase();
    return description === canonical || description === name.toLowerCase();
  });
}

export function MaterialsChecklist5333({
  items,
  onChange,
}: {
  items: MaterialLine[];
  onChange: (items: MaterialLine[]) => void;
}) {
  const [showCustom, setShowCustom] = useState(false);

  function replace(index: number, patch: Partial<MaterialLine>) {
    onChange(items.map((item, i) =>
      i === index ? { ...item, ...patch } : item
    ));
  }

  const standardIndices = new Set(
    choices.flatMap(choice => {
      const index = matchingIndex(items, choice.name, choice.unit);
      return index < 0 ? [] : [index];
    })
  );

  const customIndices = items.map((_, index) => index)
    .filter(index => !standardIndices.has(index));

  return (
    <section aria-label="Materials Included"
      style={{gridColumn:'1 / -1',marginTop:12,marginBottom:16}}>
      <h3>Materials Included</h3>
      <p className="muted">
        Select all materials included in the project. Enter the agreed
        quantity and confirm the unit. Individual selling prices are not used.
        For submitted records, confirmed units are saved through a new
        manager correction. Earlier versions stay unchanged.
      </p>

      <div style={{
        display:'grid',
        gridTemplateColumns:'repeat(auto-fit,minmax(255px,1fr))',
        gap:12
      }}>
        {choices.map(choice => {
          const description = `${choice.name} (${choice.unit})`;
          const index = matchingIndex(items, choice.name, choice.unit);
          const selected = index >= 0;
          const needsConfirmation = selected &&
            items[index].description !== description;

          return (
            <div key={description}
              style={{paddingBottom:5}}>
              <label style={{
                display:'flex',
                alignItems:'center',
                gap:8,
                width:'auto',
                margin:0
              }}>
                <input type="checkbox"
                  checked={selected}
                  style={{width:18,height:18,minWidth:18,margin:0}}
                  onChange={event => {
                    if (event.target.checked) {
                      if (!selected && items.length < 100) {
                        onChange([...items, {
                          description,
                          quantity:'1'
                        }]);
                      }
                    } else if (selected) {
                      onChange(items.filter((_, i) => i !== index));
                    }
                  }}
                />
                <span>{choice.name} ({choice.unit})</span>
              </label>

              {selected &&
                <label style={{marginTop:5}}>
                  Agreed quantity
                  <input
                    aria-label={`${choice.name} quantity`}
                    type="number"
                    min="0.01"
                    step="any"
                    value={items[index].quantity}
                    onChange={event => replace(index, {
                      quantity:event.target.value
                    })}
                  />
                </label>}

              {needsConfirmation &&
                <div style={{marginTop:6}}>
                  <p className="muted">
                    Saved earlier without a unit. Confirm that
                    {` ${choice.unit} `}is correct.
                  </p>
                  <button type="button" className="quiet"
                    onClick={() => replace(index, {description})}>
                    Confirm unit: {choice.unit}
                  </button>
                </div>}
            </div>
          );
        })}
      </div>

      <div style={{marginTop:18}}>
        <strong>Other Materials ? Describe</strong>
        <p className="muted">
          Use this only for materials not listed above.
          Include the measuring unit in each description.
        </p>

        {(customIndices.length > 0 || showCustom) &&
          customIndices.map(index => (
            <div key={index}
              style={{display:'flex',gap:10,
                flexWrap:'wrap',alignItems:'end',marginBottom:10}}>
              <label style={{flex:'2 1 220px'}}>
                Material and unit
                <input
                  aria-label={`Other material ${index + 1}`}
                  value={items[index].description}
                  onChange={event => replace(index, {
                    description:event.target.value
                  })}
                />
              </label>
              <label style={{flex:'1 1 100px'}}>
                Quantity
                <input
                  type="number"
                  aria-label={`Other material quantity ${index + 1}`}
                  min="0.01"
                  step="any"
                  value={items[index].quantity}
                  onChange={event => replace(index, {
                    quantity:event.target.value
                  })}
                />
              </label>
              <button type="button" className="quiet"
                onClick={() => onChange(
                  items.filter((_, i) => i !== index)
                )}>
                Remove
              </button>
            </div>
          ))}

        {customIndices.length === 0 && !showCustom &&
          <p className="muted">No additional materials.</p>}

        <button type="button" className="quiet"
          disabled={items.length >= 100}
          onClick={() => {
            setShowCustom(true);
            onChange([...items, {
              description:'',
              quantity:'1'
            }]);
          }}>
          Add other material
        </button>
      </div>
    </section>
  );
}
