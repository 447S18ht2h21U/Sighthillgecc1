/**
 * TEST-ONLY Weekly Payroll register presentation.
 * All rows must be fictional or independently authorized before use.
 * This component itself NEVER authorizes manager visibility.
 *
 * No backend fetch, database writes, payment approvals, exports,
 * disbursements, or live operational registration.
 */
import React from 'react';

export type WeeklyRow4344 = Readonly<{
  reference: string;
  recipient: string;
  category: 'employee' | 'contractor';
  periodStart: string;
  periodEnd: string;
  amount: string;
  managerApproval: 'PENDING' | 'APPROVED';
  comptrollerApproval: 'PENDING' | 'APPROVED';
  scheduledDate: string | null;
  recordedStatus: 'DRAFT' | 'APPROVED' | 'PAID';
  actualPaidDate: null;
  actualPaidDateVerified: false;
  exception: boolean;
}>;

export type WeeklyRegister4344 = Readonly<{
  view: 'fictional_weekly_register_only';
  historicalRoleBindingVerified: false;
  managerAccessAuthorized: false;
  livePayrollAuthorized: false;
  rows: readonly WeeklyRow4344[];
}>;

function iso(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00.000Z`);
  return Number.isFinite(date.getTime()) &&
    date.toISOString().slice(0, 10) === value;
}

function scheduledWednesday(start: string): string {
  const monday = new Date(`${start}T00:00:00.000Z`);
  const date = new Date(monday.getTime());
  date.setUTCDate(date.getUTCDate() + 9);
  return date.toISOString().slice(0, 10);
}

function validate(report: WeeklyRegister4344): void {
  if (!report || report.view !== 'fictional_weekly_register_only' ||
      report.historicalRoleBindingVerified !== false ||
      report.managerAccessAuthorized !== false ||
      report.livePayrollAuthorized !== false ||
      !Array.isArray(report.rows) ||
      report.rows.length > 100) {
    throw new Error('Unsafe fictional payroll register.');
  }

  const references = new Set<string>();

  for (const row of report.rows) {
    if (!row || typeof row !== 'object' ||
        !['employee', 'contractor'].includes(row.category) ||
        typeof row.reference !== 'string' ||
        !/^TEST-[A-Z0-9-]{1,30}$/.test(row.reference) ||
        references.has(row.reference) ||
        typeof row.recipient !== 'string' ||
        !/^Fictional [A-Za-z ]{1,60}$/.test(row.recipient) ||
        !iso(row.periodStart) ||
        !iso(row.periodEnd) ||
        row.periodStart > row.periodEnd) {
      throw new Error('Invalid fictional payroll row.');
    }

    references.add(row.reference);

    const monday = new Date(`${row.periodStart}T00:00:00.000Z`);
    const sunday = new Date(`${row.periodEnd}T00:00:00.000Z`);
    const days = (sunday.getTime() - monday.getTime()) / 86400000;

    if (monday.getUTCDay() !== 1 ||
        sunday.getUTCDay() !== 0 ||
        days !== 6 ||
        typeof row.amount !== 'string' ||
        !/^(?:0|[1-9]\d*)\.\d{2}$/.test(row.amount) ||
        !Number.isSafeInteger(Number(row.amount) * 100) ||
        !['PENDING', 'APPROVED'].includes(row.managerApproval) ||
        !['PENDING', 'APPROVED'].includes(row.comptrollerApproval) ||
        !['DRAFT', 'APPROVED', 'PAID'].includes(row.recordedStatus) ||
        typeof row.exception !== 'boolean') {
      throw new Error('Invalid payroll period, amount or approval.');
    }

    if (row.comptrollerApproval === 'APPROVED' &&
        row.managerApproval !== 'APPROVED') {
      throw new Error('Comptroller approval lacks first approval.');
    }

    if (row.recordedStatus !== 'DRAFT' &&
        (row.managerApproval !== 'APPROVED' ||
         row.comptrollerApproval !== 'APPROVED')) {
      throw new Error('Recorded approval state is inconsistent.');
    }

    if (row.scheduledDate !== null &&
        (typeof row.scheduledDate !== 'string' ||
         !iso(row.scheduledDate) ||
         row.scheduledDate !== scheduledWednesday(row.periodStart))) {
      throw new Error('Invalid scheduled Wednesday.');
    }

    if (row.actualPaidDate !== null ||
        row.actualPaidDateVerified !== false) {
      throw new Error('Unverified actual payment dates are forbidden.');
    }
  }
}

function dollars(amount: string): string {
  const number = Number(amount);
  if (!Number.isFinite(number)) throw new Error('Invalid money.');
  return '$' + number.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function approval(value: 'PENDING' | 'APPROVED'): string {
  return value === 'APPROVED' ? 'Recorded approved' : 'Pending';
}

export function PayrollWeeklyRegister4344({
  report,
}: {
  report: WeeklyRegister4344;
}): React.JSX.Element {
  validate(report);

  const cell: React.CSSProperties = {
    textAlign: 'left',
    padding: 10,
    verticalAlign: 'top',
    borderBottom: '1px solid #D7E3E7',
  };

  return (
    <section
      aria-label="Fictional weekly payroll register"
      data-test-only="true"
      style={{ color: '#142B3B' }}
    >
      <p>
        Fictional weekly register. Display testing only.
        No manager access or payment authority is granted.
      </p>

      {report.rows.length === 0 ? (
        <p>No fictional records in this period.</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {[
                  'Recipient', 'Period', 'Amount',
                  'Manager approval', 'Comptroller approval',
                  'Scheduled payment', 'Recorded status',
                  'Actual paid date', 'Exception',
                ].map(heading => (
                  <th key={heading} scope="col" style={cell}>
                    {heading}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {report.rows.map(row => (
                <tr key={row.reference}>
                  <td style={cell}>
                    {row.recipient} ({row.category})
                  </td>
                  <td style={cell}>
                    {row.periodStart} to {row.periodEnd}
                  </td>
                  <td style={cell}>{dollars(row.amount)}</td>
                  <td style={cell}>{approval(row.managerApproval)}</td>
                  <td style={cell}>{approval(row.comptrollerApproval)}</td>
                  <td style={cell}>
                    {row.scheduledDate ?? 'Not scheduled'}
                  </td>
                  <td style={cell}>
                    {row.recordedStatus === 'PAID'
                      ? 'Recorded as Paid - date unverified'
                      : row.recordedStatus === 'APPROVED'
                        ? 'Approved - Not Yet Paid'
                        : 'Draft - Not Approved'}
                  </td>
                  <td style={cell}>
                    Not independently established
                  </td>
                  <td style={cell}>
                    {row.exception ? 'Review required' : 'None recorded'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p style={{ fontSize: 13, color: '#526674' }}>
        Recorded approval is not proof of payment.
        Actual payment dates require independent verification.
        No live payroll actions or exports are enabled.
      </p>
    </section>
  );
}