/**
 * ISOLATED FICTIONAL PAYROLL REPORTS - DISPLAY ONLY.
 *
 * No real financial data, verified bank evidence, API calls,
 * PDF/Excel exports, payroll approvals or payment actions.
 *
 * This is NOT a financial calculation or authorization service.
 * All displayed totals are derived from synthetic test records.
 */
import React from 'react';

export type ReportRow4357 = Readonly<{
  reference: string;
  recipient: string;
  category: 'employee' | 'contractor';
  kind: 'COMPENSATION' | 'ADJUSTMENT';
  adjustmentOf: string | null;
  amount: string;
  recordedStatus: 'DRAFT' | 'APPROVED' | 'PAID_RECORDED';
  firstApprovalRecorded: boolean;
  comptrollerApprovalRecorded: boolean;
  auditRecorded: boolean;
  independentlyVerifiedPaidDate: null;
  independentlyVerifiedPaid: false;
  exception: boolean;
}>;

export type PayrollReport4357 = Readonly<{
  view: 'fictional_company_payroll_report_only';
  periodStart: string;
  periodEnd: string;
  backendScopeVerified: false;
  externalPaymentEvidenceVerified: false;
  exportsAvailable: false;
  livePayrollAuthorized: false;
  rows: readonly ReportRow4357[];
}>;

type Viewer4357 = 'CEO' | 'COMPTROLLER';

function validDate(value: unknown): value is string {
  if (typeof value !== 'string' ||
      !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00.000Z`);
  return Number.isFinite(date.getTime()) &&
    date.toISOString().slice(0, 10) === value;
}

function cents(amount: string): bigint {
  if (!/^(?:0|[1-9]\d{0,8})\.\d{2}$/.test(amount)) {
    throw new Error('Invalid positive compensation amount.');
  }
  const [whole, fraction] = amount.split('.');
  return BigInt(whole) * 100n + BigInt(fraction);
}

function money(value: bigint): string {
  const dollars = value / 100n;
  const fractional = (value % 100n).toString().padStart(2, '0');
  return '$' + dollars.toLocaleString('en-US') + '.' + fractional;
}

function validate(report: PayrollReport4357): void {
  if (!report ||
      report.view !== 'fictional_company_payroll_report_only' ||
      report.backendScopeVerified !== false ||
      report.externalPaymentEvidenceVerified !== false ||
      report.exportsAvailable !== false ||
      report.livePayrollAuthorized !== false ||
      !validDate(report.periodStart) ||
      !validDate(report.periodEnd) ||
      !Array.isArray(report.rows) ||
      report.rows.length > 100) {
    throw new Error('Unsafe fictional payroll report.');
  }

  const start = new Date(`${report.periodStart}T00:00:00.000Z`);
  const end = new Date(`${report.periodEnd}T00:00:00.000Z`);

  if (start.getUTCDay() !== 1 ||
      end.getUTCDay() !== 0 ||
      end.getTime() - start.getTime() !== 6 * 86400000) {
    throw new Error('Invalid Monday-Sunday payroll period.');
  }

  const refs = new Map<string, ReportRow4357>();

  for (const row of report.rows) {
    if (!row || typeof row !== 'object' ||
        typeof row.reference !== 'string' ||
        !/^TEST-[A-Z0-9-]{1,36}$/.test(row.reference) ||
        refs.has(row.reference) ||
        typeof row.recipient !== 'string' ||
        !/^Fictional [A-Za-z ]{1,60}$/.test(row.recipient) ||
        !['employee', 'contractor'].includes(row.category) ||
        !['COMPENSATION', 'ADJUSTMENT'].includes(row.kind) ||
        !['DRAFT', 'APPROVED', 'PAID_RECORDED']
          .includes(row.recordedStatus) ||
        typeof row.firstApprovalRecorded !== 'boolean' ||
        typeof row.comptrollerApprovalRecorded !== 'boolean' ||
        typeof row.auditRecorded !== 'boolean' ||
        row.independentlyVerifiedPaidDate !== null ||
        row.independentlyVerifiedPaid !== false ||
        typeof row.exception !== 'boolean') {
      throw new Error('Invalid fictional payroll report record.');
    }

    if (row.kind === 'COMPENSATION') {
      if (row.adjustmentOf !== null) {
        throw new Error('Compensation cannot replace historical records.');
      }
      cents(row.amount);
    } else {
      if (row.recordedStatus !== 'DRAFT' ||
          typeof row.adjustmentOf !== 'string' ||
          !/^TEST-[A-Z0-9-]{1,36}$/.test(row.adjustmentOf) ||
          row.adjustmentOf === row.reference ||
          typeof row.amount !== 'string' ||
          !/^-?(?:0|[1-9]\d{0,8})\.\d{2}$/.test(row.amount)) {
        throw new Error('Unverified adjustment must remain separate.');
      }
      cents(row.amount.replace(/^-/, ''));
    }

    const hasFinalApproval = row.recordedStatus !== 'DRAFT';

    if (
      (hasFinalApproval && (
        !row.firstApprovalRecorded ||
        !row.comptrollerApprovalRecorded ||
        !row.auditRecorded
      )) ||
      (!hasFinalApproval && (
        row.firstApprovalRecorded ||
        row.comptrollerApprovalRecorded ||
        row.auditRecorded
      )) ||
      (row.comptrollerApprovalRecorded &&
        !row.firstApprovalRecorded)
    ) {
      throw new Error('Missing or inconsistent payroll approvals.');
    }

    refs.set(row.reference, row);
  }

  for (const row of report.rows) {
    if (row.kind === 'ADJUSTMENT') {
      const original = refs.get(row.adjustmentOf!);
      if (!original ||
          original.kind !== 'COMPENSATION' ||
          original.recipient !== row.recipient ||
          original.category !== row.category) {
        throw new Error('Adjustment has no matching original obligation.');
      }
    }
  }
}

function totals(report: PayrollReport4357) {
  let approved = 0n;
  let recordedPaidUnverified = 0n;
  let exceptions = 0;
  let adjustments = 0;

  for (const row of report.rows) {
    if (row.exception) exceptions++;

    if (row.kind === 'ADJUSTMENT') {
      adjustments++;
      continue;
    }

    if (row.recordedStatus !== 'DRAFT') {
      approved += cents(row.amount);
    }

    if (row.recordedStatus === 'PAID_RECORDED') {
      recordedPaidUnverified += cents(row.amount);
    }
  }

  // No independently verified paid amounts are permitted by this
  // synthetic report contract. Never infer payment from PAID_RECORDED.
  const verifiedPaid = 0n;

  return {
    approved,
    verifiedPaid,
    recordedPaidUnverified,
    notVerifiedAsPaid: approved - verifiedPaid,
    exceptions,
    adjustments,
  };
}

export function PayrollReports4357({
  report,
  viewer,
}: {
  report: PayrollReport4357;
  viewer: Viewer4357;
}): React.JSX.Element {
  validate(report);

  if (viewer !== 'CEO' && viewer !== 'COMPTROLLER') {
    throw new Error('Company-wide fictional report restricted.');
  }

  const summary = totals(report);

  const metrics = [
    ['Approved obligations', money(summary.approved)],
    ['Independently verified paid', money(summary.verifiedPaid)],
    ['Not verified as paid', money(summary.notVerifiedAsPaid)],
    ['Recorded paid, evidence pending',
      money(summary.recordedPaidUnverified)],
    ['Exception records', String(summary.exceptions)],
    ['Separate draft adjustments', String(summary.adjustments)],
  ] as const;

  const cell: React.CSSProperties = {
    textAlign: 'left',
    padding: '10px 12px',
    borderBottom: '1px solid #D7E3E7',
    whiteSpace: 'nowrap',
  };

  return (
    <div
      data-test-only="true"
      aria-label="Fictional company payroll reports"
      style={{ color: '#142B3B' }}
    >
      <p>
        <strong>Reporting period:</strong> {report.periodStart}
        {' '}to{' '}{report.periodEnd}
      </p>
      <p>
        Fictional management reporting only. The database and verified
        payment evidence must be the source of truth before live use.
      </p>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 12,
        margin: '16px 0',
      }}>
        {metrics.map(([label, value]) => (
          <div key={label} style={{
            border: '1px solid #D7E3E7',
            borderRadius: 8,
            padding: 14,
            backgroundColor: '#F7F8F5',
          }}>
            <div style={{ fontSize: 13 }}>{label}</div>
            <strong style={{ fontSize: 22 }}>{value}</strong>
          </div>
        ))}
      </div>

      <p>
        Report detail (fictional). Draft adjustments are shown
        separately and are not included in approved obligations.
      </p>

      <div style={{ overflowX: 'auto' }}>
        <table style={{
          width: '100%',
          minWidth: 1100,
          borderCollapse: 'collapse',
        }}>
          <thead>
            <tr>
              {[
                'Recipient', 'Type', 'Amount', 'Recorded status',
                'Approval evidence', 'Verified payment',
                'Exception / adjustment',
              ].map(label => (
                <th scope="col" key={label} style={cell}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {report.rows.map(row => (
              <tr key={row.reference}>
                <td style={cell}>{row.recipient}</td>
                <td style={cell}>{row.category}</td>
                <td style={cell}>
                  {row.amount.startsWith('-') ? '-' : ''}
                  {money(cents(row.amount.replace(/^-/, '')))}
                </td>
                <td style={cell}>
                  {row.recordedStatus === 'PAID_RECORDED'
                    ? 'Recorded as Paid - verification pending'
                    : row.recordedStatus === 'APPROVED'
                      ? 'Approved - Not Yet Paid'
                      : 'Draft - Not Approved'}
                </td>
                <td style={cell}>
                  {row.auditRecorded
                    ? 'Fictional approvals recorded'
                    : 'Not fully approved'}
                </td>
                <td style={cell}>
                  Not independently verified
                </td>
                <td style={cell}>
                  {row.kind === 'ADJUSTMENT'
                    ? `Draft adjustment to ${row.adjustmentOf}`
                    : row.exception
                      ? 'Review required'
                      : 'None recorded'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p style={{ fontSize: 13, color: '#526674' }}>
        Approved is not Paid. Recorded Paid is not independently
        verified Paid. Draft adjustments do not change approved
        historical totals. PDF and Excel exports are disabled.
        Tax reporting requires verified payment dates and separate
        backend authorization.
      </p>
    </div>
  );
}