/**
 * Isolated approved visual refinements.
 * Receives only synthetic, previously mapped personal-payroll data.
 * No authentication, API access, approval, export, or payment authority.
 */
import React from 'react';

import type {
  PersonalReport4334,
} from './payroll-personal-records-4334';

type Row4341 = PersonalReport4334['employeeRecords'][number];

function evidenceLabel(status: string): string {
  if (status === 'NOT_ISSUED') return 'Not issued';
  if (status === 'TEST_ONLY_UNVERIFIED') {
    return 'Verification pending (fictional)';
  }
  return 'Evidence verification not established';
}

function displayStatus(row: Row4341): string {
  if (row.status === 'APPROVED' &&
      row.statusLabel === 'Approved - Not Yet Paid') {
    return 'Approved - Not Yet Paid';
  }

  if (row.status === 'PAID' && row.statusLabel === 'Paid') {
    return 'Recorded as Paid - actual date not verified';
  }

  throw new Error('Conflicting payroll payment status.');
}

export function PayrollPersonalRecords4341({
  report,
}: {
  report: PersonalReport4334;
}): React.JSX.Element {
  if (
    report.view !== 'my_payroll_test_only' ||
    report.livePayrollAuthorized !== false ||
    report.paymentActionsAvailable !== false ||
    report.exportsAvailable !== false
  ) {
    throw new Error('Unsafe payroll display contract.');
  }

  const records = [
    ...report.employeeRecords,
    ...report.contractorRecords,
  ];

  for (const row of records) {
    if (
      !['employee', 'contractor'].includes(row.compensationType) ||
      row.scheduledPaymentDate !== null ||
      row.actualPaidDate !== null ||
      row.actualPaidDateVerified !== false
    ) {
      throw new Error('Unverified payroll field cannot be displayed.');
    }

    displayStatus(row);
  }

  const cell: React.CSSProperties = {
    textAlign: 'left',
    padding: '12px 10px',
    borderBottom: '1px solid #D7E3E7',
    verticalAlign: 'top',
  };

  return (
    <div
      aria-label="Test-only personal payroll records"
      data-test-only="true"
      style={{ color: '#142B3B' }}
    >
      <p>
        <strong>Report period:</strong> {report.periodStart}
        {' '}through{' '}{report.periodEnd}
      </p>

      <p style={{ fontSize: 14 }}>
        Fictional payroll records for visual testing only.
      </p>

      {records.length === 0 ? (
        <p>No approved or paid records in this period.</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
            }}
          >
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
                ].map(heading => (
                  <th scope="col" key={heading} style={cell}>
                    {heading}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {records.map((row, index) => (
                <tr key={`${row.compensationType}-${index}`}>
                  <td style={cell}>{row.compensationType}</td>
                  <td style={cell}>
                    {row.periodStart} to {row.periodEnd}
                  </td>
                  <td style={cell}>{row.compensationKind}</td>
                  <td style={cell}>{row.amount}</td>
                  <td style={cell}>{displayStatus(row)}</td>
                  <td style={cell}>
                    {evidenceLabel(row.paymentEvidenceStatus)}
                  </td>
                  <td style={cell}>
                    Not independently established
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p style={{ fontSize: 13, color: '#526674' }}>
        A recorded Paid status does not establish an independently
        verified disbursement date. Payment actions and report
        exports remain disabled.
      </p>
    </div>
  );
}