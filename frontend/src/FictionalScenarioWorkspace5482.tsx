import { useFictionalScenario } from './FictionalFinancialScenario5481';

type Workspace = 'payroll' | 'financial';
const PRICE = 1350000;

function parseCents(value: string): number | null {
  if (!/^\d+(\.\d{1,2})?$/.test(value.trim())) return null;
  const n = Number(value);
  if (!Number.isFinite(n) || n > 100000000) return null;
  return Math.round(n * 100);
}

function parseHours(value: string): number | null {
  if (!/^\d+(\.\d{1,2})?$/.test(value.trim())) return null;
  const n = Number(value);
  if (!Number.isFinite(n) || n > 10000) return null;
  return Math.round(n * 100);
}

function money(value: number): string {
  return (value / 100).toLocaleString('en-US', {
    style: 'currency', currency: 'USD',
  });
}

function Line({ label, amount, total = false }: {
  label: string;
  amount: number;
  total?: boolean;
}) {
  return <div style={{
    display: 'flex',
    justifyContent: 'space-between',
    gap: 12,
    padding: '6px 0',
    borderBottom: total ? '2px solid #142B3B' : '1px solid #D7E3E7',
    fontWeight: total ? 700 : 400,
  }}>
    <span>{label}</span>
    <span style={{ whiteSpace: 'nowrap' }}>{money(amount)}</span>
  </div>;
}

export default function FictionalScenarioWorkspace5482({
  workspace,
}: {
  workspace: Workspace;
}) {
  const input = useFictionalScenario();
  const values = [
    input.payment, input.equipment, input.materials,
    input.dealerFee, input.leadCost, input.otherVendor,
    input.vendorPaid, input.hourlyRate,
  ].map(parseCents);

  const hours = parseHours(input.hours);
  const [
    customerPaid, equipment, materials, dealer,
    lead, other, vendorPaid, rate,
  ] = values.map(value => value ?? 0);

  const vendorInvoices = equipment + materials + dealer + lead + other;
  const valid = values.every(value => value !== null)
    && hours !== null
    && customerPaid <= PRICE
    && vendorPaid <= vendorInvoices;

  const technician = Math.round(rate * (hours ?? 0) / 100);
  const gross = PRICE - vendorInvoices - technician;

  let firstCommission = gross > 0 ? Math.round(gross * 0.15) : 0;
  let secondCommission = gross > 0 ? Math.round(gross * 0.05) : 0;

  if (gross - firstCommission - secondCommission <= 0) {
    firstCommission = 0;
    secondCommission = 0;
  }

  const commissions = firstCommission + secondCommission;
  const income = gross - commissions;
  const receivable = PRICE - customerPaid;
  const payable = vendorInvoices - vendorPaid;
  const cash = customerPaid - vendorPaid;
  const assets = cash + receivable;
  const liabilities = payable + technician + commissions;

  const cardStyle = {
    padding: 14,
    border: '1px solid #D7E3E7',
    borderRadius: 8,
    background: '#fff',
    minWidth: 0,
  };

  return <section
    aria-label="Fictional project financial scenario"
    style={{
      margin: '18px 0',
      padding: 18,
      background: '#F7F8F5',
      border: '2px dashed #087F75',
      borderRadius: 8,
    }}
  >
    <h3>Project 104 ? Shared Financial Scenario</h3>
    <p><strong>SIMULATED ? NOT ACTUAL PAYROLL OR ACCOUNTING</strong></p>
    <p>
      These figures use your inputs from Customer Payments.
      They remain in browser memory only and are not saved.
    </p>

    {!valid ? <p role="alert">
      Scenario inputs are invalid. Correct the amounts or hours
      in Customer Payments.
    </p> : workspace === 'payroll' ? <>
      <h4>Hypothetical Weekly Payroll</h4>
      <div style={cardStyle}>
        <Line label="Technician ? proposed hourly earnings"
          amount={technician} />
        <Line label="Legacy 15% commission illustration"
          amount={firstCommission} />
        <Line label="Legacy 5% commission illustration"
          amount={secondCommission} />
        <Line label="Total illustrative compensation"
          amount={technician + commissions} total />
      </div>
      <p>
        No technician hours or earnings are verified.
        Commission beneficiaries remain unresolved.
        No payroll obligations or payments are created.
      </p>
    </> : <>
      <h4>Hypothetical Corporate Financial Statements</h4>
      <p>
        Project-only accrual illustration, assuming recognized
        revenue and expenses and zero opening balances.
        Not an official corporate report.
      </p>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))',
        gap: 12,
      }}>
        <div style={cardStyle}>
          <h4>Income Statement</h4>
          <Line label="Revenue" amount={PRICE} />
          <Line label="Vendor expenses" amount={-vendorInvoices} />
          <Line label="Technician expense" amount={-technician} />
          <Line label="Gross profit" amount={gross} total />
          <Line label="Illustrative commissions" amount={-commissions} />
          <Line label="Net income" amount={income} total />
        </div>
        <div style={cardStyle}>
          <h4>Balance Sheet</h4>
          <Line label="Net cash movement" amount={cash} />
          <Line label="Customer receivable" amount={receivable} />
          <Line label="Total assets" amount={assets} total />
          <Line label="Vendor accounts payable" amount={payable} />
          <Line label="Technician accrual" amount={technician} />
          <Line label="Illustrative commission accrual"
            amount={commissions} />
          <Line label="Total liabilities" amount={liabilities} />
          <Line label="Illustrative equity" amount={income} />
          <Line label="Liabilities plus equity"
            amount={liabilities + income} total />
          <p><strong>
            {assets === liabilities + income
              ? 'Scenario balances'
              : 'Scenario does not balance'}
          </strong></p>
        </div>
        <div style={cardStyle}>
          <h4>Cash Flow Statement</h4>
          <Line label="Hypothetical customer receipts"
            amount={customerPaid} />
          <Line label="Vendor bills paid" amount={-vendorPaid} />
          <Line label="Technician payments" amount={0} />
          <Line label="Commission payments" amount={0} />
          <Line label="Net cash movement" amount={cash} total />
          <p>Unpaid expenses do not reduce cash until paid.</p>
        </div>
      </div>
    </>}

    <p style={{ fontSize: 12, marginTop: 14 }}>
      ACCEPTANCE SIMULATION ONLY. No real customer payment,
      bank confirmation, commission, payroll obligation,
      or official corporate report is created.
    </p>
  </section>;
}
