import React from 'react';

/**
 * VERIDIAN payroll design preview -- FICTIONAL DATA ONLY.
 * Not registered in main.tsx, not a live payroll report, and not
 * an authorization, approval, or payment interface.
 */
type PreviewRow = Readonly<{
  label: string;
  project: string;
  amount: string;
  state: string;
}>;

const fictionalRows: readonly PreviewRow[] = [
  {
    label: 'Fictional Contractor A',
    project: 'DEMO-001',
    amount: '$750.00',
    state: 'Approved - Not Yet Paid',
  },
  {
    label: 'Fictional Contractor B',
    project: 'DEMO-002',
    amount: '$500.00',
    state: 'Pending approval',
  },
];

const outer: React.CSSProperties = {
  maxWidth: 1100,
  margin: '0 auto',
  padding: 24,
  color: '#142B3B',
  fontFamily: 'Inter, Arial, sans-serif',
};
const card: React.CSSProperties = {
  border: '1px solid #D7E3E7',
  borderRadius: 12,
  backgroundColor: '#FFFFFF',
  padding: 22,
  marginBottom: 20,
};
const muted: React.CSSProperties = { color: '#526674' };
const table: React.CSSProperties = {
  borderCollapse: 'collapse',
  width: '100%',
};
const cell: React.CSSProperties = {
  textAlign: 'left',
  padding: 10,
  borderBottom: '1px solid #D7E3E7',
};

export function PayrollDesignPreview4281(): React.JSX.Element {
  return (
    <main style={outer} aria-label="VERIDIAN fictional payroll design review">
      <h1>VERIDIAN Payroll &amp; Compensation</h1>
      <p role="note" style={{
        backgroundColor: '#F7F8F5',
        borderLeft: '5px solid #C39A58',
        padding: 16,
      }}>
        <strong>FICTIONAL DATA - DESIGN REVIEW ONLY.</strong>{' '}
        No real employee records, payment approval, or payment issuance.
      </p>

      <section data-view="my-compensation" style={card}>
        <h2>1. My Compensation</h2>
        <p style={muted}>
          Personal records only. Operational identity and permission checks
          must happen on the protected backend.
        </p>
        <table style={table}>
          <thead>
            <tr>
              <th style={cell}>Pay period</th>
              <th style={cell}>Type</th>
              <th style={cell}>Status</th>
              <th style={cell}>Scheduled payment</th>
              <th style={cell}>Amount</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={cell}>Nov 2-8, 2026</td>
              <td style={cell}>Commission</td>
              <td style={cell}>Approved - Not Yet Paid</td>
              <td style={cell}>Nov 11, 2026</td>
              <td style={cell}>$1,250.00</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section data-view="payroll-review" style={card}>
        <h2>2. Payroll Review &amp; Approval</h2>
        <p style={muted}>
          Manager and Comptroller views require different backend
          permissions. These rows cannot approve or issue payments.
        </p>
        <table style={table}>
          <thead>
            <tr>
              <th style={cell}>Contractor</th>
              <th style={cell}>Project</th>
              <th style={cell}>Earned date</th>
              <th style={cell}>Scheduled Wednesday</th>
              <th style={cell}>Actual paid date</th>
              <th style={cell}>Amount</th>
              <th style={cell}>Status</th>
            </tr>
          </thead>
          <tbody>
            {fictionalRows.map((row) => (
              <tr key={row.project}>
                <td style={cell}>{row.label}</td>
                <td style={cell}>{row.project}</td>
                <td style={cell}>Nov 3, 2026</td>
                <td style={cell}>Nov 11, 2026</td>
                <td style={cell}>Not paid</td>
                <td style={cell}>{row.amount}</td>
                <td style={cell}>{row.state}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p style={muted}>
          The production register must also show independent approvals,
          payment references, adjustments, and audit history.
        </p>
      </section>

      <section data-view="company-summary" style={card}>
        <h2>3. Company Payroll Summary</h2>
        <p style={muted}>
          CEO and Comptroller only. Illustration is not an actual
          payroll calculation.
        </p>
        <dl style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
          gap: 12,
        }}>
          <div><dt>Contractors</dt><dd>$8,500.00</dd></div>
          <div><dt>Employees</dt><dd>$4,000.00</dd></div>
          <div><dt>Verified paid total</dt><dd>$12,500.00</dd></div>
        </dl>
        <p style={muted}>
          Approved-but-unpaid compensation must not be counted as paid.
          Reports must reconcile to backend-verified payment evidence.
        </p>
      </section>
    </main>
  );
}