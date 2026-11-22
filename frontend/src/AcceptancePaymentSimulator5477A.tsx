import { useScenarioInput } from './FictionalFinancialScenario5481';

const PROJECT_TOTAL_CENTS = 1350000;

const money = (cents: number) =>
  (cents / 100).toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
  });

function parseMoney(value: string): number | null {
  if (!/^\d+(\.\d{1,2})?$/.test(value.trim())) return null;
  const amount = Number(value);
  if (!Number.isFinite(amount) || amount > 100000000) return null;
  return Math.round(amount * 100);
}

function parseHours(value: string): number | null {
  if (!/^\d+(\.\d{1,2})?$/.test(value.trim())) return null;
  const hours = Number(value);
  if (!Number.isFinite(hours) || hours > 10000) return null;
  return Math.round(hours * 100);
}

type MoneyInputProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
};

function MoneyInput({ label, value, onChange }: MoneyInputProps) {
  return (
    <label style={{ display: 'block' }}>
      {label}
      <input
        aria-label={label}
        type="number"
        min="0"
        max="100000000"
        step="0.01"
        value={value}
        onChange={event => onChange(event.target.value)}
        style={{ display: 'block', width: '100%', marginTop: 6 }}
      />
    </label>
  );
}

function StatementLine({
  name, amount, strong = false,
}: {
  name: string;
  amount: number;
  strong?: boolean;
}) {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      gap: 16,
      padding: '7px 0',
      borderBottom: strong ? '2px solid #142B3B' : '1px solid #D7E3E7',
      fontWeight: strong ? 700 : 400,
    }}>
      <span>{name}</span>
      <span style={{ whiteSpace: 'nowrap' }}>{money(amount)}</span>
    </div>
  );
}

export default function AcceptancePaymentSimulator5477A() {
  const [payment, setPayment] = useScenarioInput('payment');
  const [equipment, setEquipment] = useScenarioInput('equipment');
  const [materials, setMaterials] = useScenarioInput('materials');
  const [dealerFee, setDealerFee] = useScenarioInput('dealerFee');
  const [leadCost, setLeadCost] = useScenarioInput('leadCost');
  const [otherVendor, setOtherVendor] = useScenarioInput('otherVendor');
  const [vendorPaid, setVendorPaid] = useScenarioInput('vendorPaid');
  const [hours, setHours] = useScenarioInput('hours');
  const [hourlyRate, setHourlyRate] = useScenarioInput('hourlyRate');

  const amounts = [
    payment, equipment, materials, dealerFee,
    leadCost, otherVendor, vendorPaid, hourlyRate,
  ].map(parseMoney);
  const parsedHours = parseHours(hours);

  const validValues =
    amounts.every(value => value !== null) && parsedHours !== null;

  const [
    customerPaid, equipmentCost, materialCost, dealer,
    lead, other, vendorsPaid, rate,
  ] = amounts.map(value => value ?? 0);

  const vendorInvoices =
    equipmentCost + materialCost + dealer + lead + other;

  const technicianCost = Math.round(rate * (parsedHours ?? 0) / 100);

  const valid =
    validValues &&
    customerPaid <= PROJECT_TOTAL_CENTS &&
    vendorsPaid <= vendorInvoices;

  // Legacy commission rates are shown only as hypothetical examples.
  // No recipient, entitlement, approval or payable record is created.
  const grossProfit = PROJECT_TOTAL_CENTS - vendorInvoices - technicianCost;

  let firstCommission = grossProfit > 0
    ? Math.round(grossProfit * 0.15)
    : 0;
  let secondCommission = grossProfit > 0
    ? Math.round(grossProfit * 0.05)
    : 0;

  if (grossProfit - firstCommission - secondCommission <= 0) {
    firstCommission = 0;
    secondCommission = 0;
  }

  const commissionTotal = firstCommission + secondCommission;
  const netIncome = grossProfit - commissionTotal;

  const accountsReceivable = PROJECT_TOTAL_CENTS - customerPaid;
  const accountsPayable = vendorInvoices - vendorsPaid;
  const unpaidTechnician = technicianCost;
  const unpaidCommissions = commissionTotal;

  const netCashMovement = customerPaid - vendorsPaid;
  const totalAssets = netCashMovement + accountsReceivable;
  const totalLiabilities =
    accountsPayable + unpaidTechnician + unpaidCommissions;
  const liabilitiesAndEquity = totalLiabilities + netIncome;
  const reconciles = totalAssets === liabilitiesAndEquity;

  const formGrid: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
    gap: 14,
    marginTop: 12,
  };

  const statementStyle: React.CSSProperties = {
    border: '1px solid #D7E3E7',
    borderRadius: 8,
    padding: 16,
    background: '#fff',
    minWidth: 0,
  };

  return (
    <section
      aria-label="Fictional Project Financial Scenario"
      style={{
        margin: '20px 0',
        padding: 18,
        background: '#F7F8F5',
        border: '2px dashed #087F75',
        borderRadius: 8,
      }}
    >
      <h3>Project Financial Scenario</h3>
      <p><strong>SIMULATED ? NOT ACTUAL PAYMENT OR ACCOUNTING</strong></p>
      <p>
        Project 104-SA-2026-11-22 ? GECC Test Customer.
        All figures below are fictional planning assumptions.
        No transactions or approvals are saved.
      </p>
      <p>
        <strong>Approved fictional project price: {money(PROJECT_TOTAL_CENTS)}</strong>
      </p>

      <h4>1. Customer payment scenario</h4>
      <div style={formGrid}>
        <MoneyInput
          label="Hypothetical payment amount ($)"
          value={payment}
          onChange={setPayment}
        />
      </div>
      <p>
        Customer payment is an illustrative cash receipt, not verified funds.
      </p>

      <h4>2. Hypothetical vendor invoices</h4>
      <p>
        These amounts represent vendor bills received and expenses incurred.
        They are not taken from MSR material estimates.
      </p>
      <div style={formGrid}>
        <MoneyInput label="Equipment invoices ($)" value={equipment}
          onChange={setEquipment} />
        <MoneyInput label="Material invoices ($)" value={materials}
          onChange={setMaterials} />
        <MoneyInput label="Dealer fees ($)" value={dealerFee}
          onChange={setDealerFee} />
        <MoneyInput label="Lead expenses ($)" value={leadCost}
          onChange={setLeadCost} />
        <MoneyInput label="Other vendor expenses ($)" value={otherVendor}
          onChange={setOtherVendor} />
        <MoneyInput label="Vendor invoices actually paid in scenario ($)"
          value={vendorPaid} onChange={setVendorPaid} />
      </div>
      <p>
        Receiving an invoice creates a hypothetical expense and payable.
        Only the amount entered as paid changes the cash-flow scenario.
      </p>

      <h4>3. Technician compensation scenario</h4>
      <div style={formGrid}>
        <MoneyInput label="Proposed hourly rate ($)" value={hourlyRate}
          onChange={setHourlyRate} />
        <label style={{ display: 'block' }}>
          Hypothetical hours worked
          <input
            aria-label="Hypothetical hours worked"
            type="number"
            min="0"
            max="10000"
            step="0.01"
            value={hours}
            onChange={event => setHours(event.target.value)}
            style={{ display: 'block', width: '100%', marginTop: 6 }}
          />
        </label>
      </div>
      <p>
        No actual hours, approved compensation, payroll obligation,
        or technician payment are asserted.
      </p>

      <h4>4. Proposed commission illustration</h4>
      <p>
        Existing legacy calculation rates: 15% and 5% of hypothetical
        project gross profit. Beneficiaries are not assigned here.
        These figures are not earned or approved commissions.
      </p>

      {!valid && (
        <p role="alert" style={{ color: '#A12622' }}>
          Enter valid nonnegative amounts with up to two decimal places.
          Customer payment cannot exceed the invoice and vendor
          payments cannot exceed vendor invoices.
        </p>
      )}

      {valid && (
        <>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: 12,
            margin: '20px 0',
          }}>
            {[
              ['Hypothetical balance', money(accountsReceivable)],
              ['Unpaid vendor invoices', money(accountsPayable)],
              ['Projected gross profit', money(grossProfit)],
              ['Projected net income', money(netIncome)],
            ].map(([label, value]) => (
              <div key={label} style={statementStyle}>
                <div style={{ fontSize: 13 }}>{label}</div>
                <strong style={{ fontSize: 20 }}>{value}</strong>
              </div>
            ))}
          </div>

          <h4>5. Illustrative corporate financial statements</h4>
          <p>
            Simplified, project-only accrual illustration with zero
            opening balances. No taxes, financing, overhead allocation,
            depreciation or other corporate transactions are included.
          </p>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(245px, 1fr))',
            gap: 14,
          }}>
            <div style={statementStyle}>
              <h4>Income Statement</h4>
              <StatementLine name="Project revenue" amount={PROJECT_TOTAL_CENTS} />
              <StatementLine name="Vendor expenses" amount={-vendorInvoices} />
              <StatementLine name="Technician expense" amount={-technicianCost} />
              <StatementLine name="Gross profit" amount={grossProfit} strong />
              <StatementLine name="15% commission illustration"
                amount={-firstCommission} />
              <StatementLine name="5% commission illustration"
                amount={-secondCommission} />
              <StatementLine name="Net income" amount={netIncome} strong />
            </div>

            <div style={statementStyle}>
              <h4>Balance Sheet</h4>
              <StatementLine name="Net cash movement" amount={netCashMovement} />
              <StatementLine name="Customer receivable" amount={accountsReceivable} />
              <StatementLine name="Total illustrative assets"
                amount={totalAssets} strong />
              <StatementLine name="Vendor accounts payable"
                amount={accountsPayable} />
              <StatementLine name="Technician payable" amount={unpaidTechnician} />
              <StatementLine name="Commission payable illustration"
                amount={unpaidCommissions} />
              <StatementLine name="Total liabilities"
                amount={totalLiabilities} />
              <StatementLine name="Illustrative retained earnings"
                amount={netIncome} />
              <StatementLine name="Liabilities plus equity"
                amount={liabilitiesAndEquity} strong />
              <p>
                <strong>
                  {reconciles ? 'Scenario balances' : 'Scenario does not balance'}
                </strong>
              </p>
            </div>

            <div style={statementStyle}>
              <h4>Cash Flow Statement</h4>
              <StatementLine name="Hypothetical customer receipts"
                amount={customerPaid} />
              <StatementLine name="Vendor bills paid"
                amount={-vendorsPaid} />
              <StatementLine name="Technician payments" amount={0} />
              <StatementLine name="Commission payments" amount={0} />
              <StatementLine name="Net operating cash movement"
                amount={netCashMovement} strong />
              <p>
                Unpaid invoices and accrued compensation do not
                reduce cash until paid.
              </p>
            </div>
          </div>

          <h4>6. Hypothetical project reconciliation</h4>
          <StatementLine name="Project price" amount={PROJECT_TOTAL_CENTS} />
          <StatementLine name="Less illustrative customer receipts"
            amount={-customerPaid} />
          <StatementLine name="Remaining customer receivable"
            amount={accountsReceivable} strong />
          <StatementLine name="Vendor bills incurred" amount={vendorInvoices} />
          <StatementLine name="Less vendor payments" amount={-vendorsPaid} />
          <StatementLine name="Remaining vendor payable"
            amount={accountsPayable} strong />
        </>
      )}

      <p style={{
        marginTop: 20,
        paddingTop: 12,
        borderTop: '1px solid #D7E3E7',
        fontSize: 13,
      }}>
        <strong>Acceptance simulation only.</strong> The real project
        remains unpaid and unfinished unless verified operational
        evidence independently establishes otherwise. This preview
        cannot authorize installation, issue a Receipt, verify bank
        availability, create commissions, approve payroll, or alter
        corporate financial reports.
      </p>
    </section>
  );
}
