import { useEffect } from 'react';

type PricingData = {
  base_price: string;
  discount: string;
  tax: string;
  total_price: string;
  financing_type?: string;
  payment_option: string;
  payment_terms: string;
  commercial_notes: string;
  marketing_promotion?: boolean;
};

function standardTerms(option: string): string {
  if (option === '50_PERCENT_DEPOSIT') {
    return '50% deposit due the day before installation; remaining 50% due after installation.';
  }
  if (option === '100_PERCENT_COMPLETION') {
    return '100% of the project price due upon completion.';
  }
  return '';
}

function calculateTotal(
  base: string,
  discount: string,
  tax: string
): string | null {
  function cents(input: string): bigint | null {
    const match = input.trim().match(/^(\d+)(?:\.(\d{1,2}))?$/);
    if (!match) return null;
    return BigInt(match[1]) * 100n +
      BigInt((match[2] ?? '').padEnd(2, '0'));
  }

  const a = cents(base);
  const b = cents(discount);
  const c = cents(tax);

  if (a === null || b === null || c === null) return null;

  const total = a - b + c;
  if (total < 0n || total > 99999999999n) return null;

  return `${total / 100n}.${(total % 100n).toString().padStart(2, '0')}`;
}

const panelStyle = {
  border: '1px solid #D7E3E7',
  borderRadius: 8,
  padding: 16,
  minWidth: 0,
};

export function SalesPricing5762<T extends PricingData>({
  value,
  onChange,
}: {
  value: T;
  onChange: (next: T) => void;
}) {
  // Fill a missing standard term, but never replace saved wording.
  useEffect(() => {
    const terms = standardTerms(value.payment_option);
    if (terms && !value.payment_terms.trim()) {
      onChange({ ...value, payment_terms: terms });
    }
  }, [value.payment_option]);

  const calculated = calculateTotal(
    value.base_price,
    value.discount,
    value.tax
  );

  const matchingTotal = calculated !== null &&
    calculated === value.total_price;

  function updatePrice(
    key: 'base_price' | 'discount' | 'tax',
    input: string
  ) {
    const next = { ...value, [key]: input };
    onChange({
      ...next,
      total_price: calculateTotal(
        next.base_price,
        next.discount,
        next.tax
      ) ?? '',
    });
  }

  return (
    <div style={{ gridColumn: '1 / -1' }}>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit,minmax(min(100%,310px),1fr))',
        gap: 20,
        alignItems: 'start',
      }}>
        <section style={panelStyle}>
          <h3 style={{ marginTop: 0 }}>Selling Price</h3>
          {([
            ['base_price', 'Base Price ($)'],
            ['discount', 'Discount ($)'],
            ['tax', 'Tax ($)'],
          ] as const).map(([key, label]) => (
            <label key={key} style={{ display: 'block', marginBottom: 14 }}>
              {label}
              <input
                aria-label={label}
                inputMode="decimal"
                value={value[key]}
                onChange={event => updatePrice(key, event.target.value)}
              />
            </label>
          ))}
          <div style={{
            background: '#F7F8F5',
            border: '1px solid #D7E3E7',
            borderRadius: 6,
            padding: 14,
          }}>
            <strong>Total Selling Price</strong>
            <div style={{ fontSize: '1.5rem', fontWeight: 800 }}>
              {value.total_price
                ? '$' + value.total_price
                : 'Check price amounts'}
            </div>
          </div>
          <p className="muted">
            Base Price - Discount + Tax = Total Selling Price.
          </p>
          {!matchingTotal && (
            <p role="alert">
              Check the amounts. The total must match the calculation.
            </p>
          )}
          {Number(value.discount) > 0 && (
            <p className="muted">
              Discounts require the applicable authorization before
              customer documents can be released.
            </p>
          )}
        </section>

        <section style={panelStyle}>
          <h3 style={{ marginTop: 0 }}>Payment Information</h3>

          <label>
            Financing
            <select
              aria-label="Financing"
              value={value.financing_type ?? ''}
              onChange={event => onChange({
                ...value,
                financing_type: event.target.value,
              })}
            >
              <option value="">Choose financing</option>
              <option value="NON_FINANCED">Non-financed</option>
              <option value="FINANCED">Financed</option>
            </select>
          </label>

          <label>
            Payment arrangement
            <select
              aria-label="Payment arrangement"
              value={value.payment_option}
              onChange={event => {
                const option = event.target.value;
                const oldStandard = standardTerms(value.payment_option);
                const hasCustom = Boolean(value.payment_terms.trim()) &&
                  value.payment_terms !== oldStandard;

                onChange({
                  ...value,
                  payment_option: option,
                  payment_terms: hasCustom
                    ? value.payment_terms
                    : standardTerms(option),
                });
              }}
            >
              <option value="">Choose payment arrangement</option>
              <option value="50_PERCENT_DEPOSIT">
                50% deposit day before installation; balance after installation
              </option>
              <option value="100_PERCENT_COMPLETION">
                100% upon completion
              </option>
              <option value="OTHER_APPROVAL_REQUIRED">
                Other - Describe proposed terms
              </option>
            </select>
          </label>

          <label>
            Payment terms
            <textarea
              rows={3}
              aria-label="Payment terms"
              value={value.payment_terms}
              onChange={event => onChange({
                ...value,
                payment_terms: event.target.value,
              })}
            />
          </label>

          <p className="muted">
            Standard payment terms fill automatically.
            Previously entered special wording is preserved.
          </p>

          {value.payment_option === 'OTHER_APPROVAL_REQUIRED' && (
            <p role="status">
              Other payment terms require separate authorization
              before submission.
            </p>
          )}

          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            width: 'auto',
            marginTop: 14,
          }}>
            <input
              type="checkbox"
              aria-label="Marketing Promotion"
              style={{ width: 18, height: 18, minWidth: 18, margin: 0 }}
              checked={value.marketing_promotion === true}
              onChange={event => onChange({
                ...value,
                marketing_promotion: event.target.checked,
              })}
            />
            <strong>Marketing Promotion</strong>
          </label>

          <p className="muted">
            This checkbox does not reduce the selling price
            or authorize a customer benefit.
          </p>

          <label>
            Special Customer Arrangements / Notes
            <textarea
              rows={3}
              aria-label="Special Customer Arrangements / Notes"
              value={value.commercial_notes}
              onChange={event => onChange({
                ...value,
                commercial_notes: event.target.value,
              })}
            />
          </label>
        </section>
      </div>
    </div>
  );
}
