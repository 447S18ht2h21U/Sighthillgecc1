/**
 * Test-only React display of an ALREADY MAPPED personal payroll report.
 * NOT an authentication boundary, operational route, or API.
 * Parent must receive data only through an authorized backend boundary.
 * This preview cannot authorize an earning date or a payment.
 */
import React from 'react';

type Row4334 = {
  compensationType: 'employee' | 'contractor';
  periodStart: string;
  periodEnd: string;
  compensationKind: string;
  amount: string;
  status: 'APPROVED' | 'PAID';
  statusLabel: string;
  paymentEvidenceStatus: string;
  scheduledPaymentDate: null;
  actualPaidDate: null;
  actualPaidDateVerified: false;
};

export type PersonalReport4334 = {
  view: 'my_payroll_test_only';
  periodStart: string;
  periodEnd: string;
  employeeRecords: readonly Row4334[];
  contractorRecords: readonly Row4334[];
  paymentActionsAvailable: false;
  exportsAvailable: false;
  livePayrollAuthorized: false;
};

export function PayrollPersonalRecords4334({
  report,
}: {
  report: PersonalReport4334;
}): React.JSX.Element {
  if (
    report.view !== 'my_payroll_test_only' ||
    report.paymentActionsAvailable !== false ||
    report.exportsAvailable !== false ||
    report.livePayrollAuthorized !== false
  ) {
    throw new Error('Payroll display contract is not safe.');
  }

  const rows = [...report.employeeRecords, ...report.contractorRecords];

  if (rows.some(row =>
    row.actualPaidDate !== null ||
    row.scheduledPaymentDate !== null ||
    row.actualPaidDateVerified !== false
  )) {
    throw new Error('Unverified payment date in payroll display.');
  }

  const cell: React.CSSProperties = {
    textAlign: 'left',
    padding: 12,
    borderBottom: '1px solid #D7E3E7',
  };

  return (
    <section
      aria-label="Test-only personal payroll records"
      data-test-only="true"
      style={{
        fontFamily: 'Inter, Arial, sans-serif',
        color: '#142B3B',
        background: '#F7F8F5',
        border: '1px solid #D7E3E7',
        borderRadius: 12,
        padding: 20,
      }}
    >
      <h2>My Payroll</h2>
      <p>
        Report period: {report.periodStart} through {report.periodEnd}
      </p>
      <p>
        Test-only authorized-format preview. No live financial actions.
      </p>

      {rows.length === 0 ? (
        <p>No approved or paid records in this period.</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {[
                  'Type',
                  'Period',
                  'Compensation',
                  'Amount',
                  'Status',
                  'Payment evidence',
                  'Actual paid date',
                ].map(title => (
                  <th scope="col" key={title} style={cell}>
                    {title}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`${row.compensationType}-${index}`}>
                  <td style={cell}>{row.compensationType}</td>
                  <td style={cell}>
                    {row.periodStart} to {row.periodEnd}
                  </td>
                  <td style={cell}>{row.compensationKind}</td>
                  <td style={cell}>{row.amount}</td>
                  <td style={cell}>{row.statusLabel}</td>
                  <td style={cell}>{row.paymentEvidenceStatus}</td>
                  <td style={cell}>Not independently established</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p style={{ fontSize: 13, color: '#526674' }}>
        A PAID status does not establish an independently verified
        disbursement date. Payment actions and report exports are disabled.
      </p>
    </section>
  );
}