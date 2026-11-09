/**
 * ISOLATED FICTIONAL PAYMENT HISTORY - DISPLAY ONLY.
 *
 * Recorded PAID is not independent evidence of disbursement.
 * Issue and settlement dates must not become actual paid dates.
 * Adjustments remain distinct from original historical obligations.
 *
 * This component provides no access, verification, payment,
 * modification, download, export or API capability.
 */
import React from 'react';

type HistoryRow4351 = Readonly<{
  reference: string;
  recipient: string;
  category: 'employee' | 'contractor';
  kind: 'COMPENSATION' | 'ADJUSTMENT';
  adjustmentOf: string | null;
  compensationDate: string | null;
  periodStart: string;
  periodEnd: string;
  amount: string;
  recordedStatus: 'DRAFT' | 'APPROVED' | 'PAID';
  proposedPaymentDate: string | null;
  issuedDate: string | null;
  settlementCandidateDate: string | null;
  method: 'ACH' | 'CHECK' | null;
  paymentReference: string | null;
  actualPaidDate: null;
  actualPaidDateVerified: false;
  exception: boolean;
}>;

export type PaymentHistory4351 = Readonly<{
  view: 'fictional_payment_history_only';
  backendScopeVerified: false;
  externalPaymentEvidenceVerified: false;
  livePaymentAuthorized: false;
  rows: readonly HistoryRow4351[];
}>;

function iso(value: unknown): value is string {
  if (typeof value !== 'string' ||
      !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return Number.isFinite(parsed.getTime()) &&
    parsed.toISOString().slice(0, 10) === value;
}

function optionalDate(value: unknown): boolean {
  return value === null || iso(value);
}

function money(value: string): string {
  const negative = value.startsWith('-');
  const absolute = negative ? value.slice(1) : value;
  const [whole, fraction] = absolute.split('.');
  const cents = Number(whole) * 100 + Number(fraction);
  if (!Number.isSafeInteger(cents)) {
    throw new Error('Unsafe payment amount.');
  }
  return `${negative ? '-' : ''}$${(cents / 100).toLocaleString(
    'en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }
  )}`;
}

function validate(report: PaymentHistory4351): void {
  if (!report || report.view !== 'fictional_payment_history_only' ||
      report.backendScopeVerified !== false ||
      report.externalPaymentEvidenceVerified !== false ||
      report.livePaymentAuthorized !== false ||
      !Array.isArray(report.rows) || report.rows.length > 100) {
    throw new Error('Untrusted Payment History report.');
  }

  const seen = new Set<string>();

  for (const row of report.rows) {
    if (!row || typeof row !== 'object' ||
        typeof row.reference !== 'string' ||
        !/^TEST-[A-Z0-9-]{1,30}$/.test(row.reference) ||
        seen.has(row.reference) ||
        typeof row.recipient !== 'string' ||
        !/^Fictional [A-Za-z ]{1,60}$/.test(row.recipient) ||
        !['employee', 'contractor'].includes(row.category) ||
        !['COMPENSATION', 'ADJUSTMENT'].includes(row.kind) ||
        !['DRAFT', 'APPROVED', 'PAID'].includes(row.recordedStatus) ||
        !iso(row.periodStart) || !iso(row.periodEnd) ||
        row.periodStart > row.periodEnd ||
        !optionalDate(row.compensationDate) ||
        !optionalDate(row.proposedPaymentDate) ||
        !optionalDate(row.issuedDate) ||
        !optionalDate(row.settlementCandidateDate) ||
        row.actualPaidDate !== null ||
        row.actualPaidDateVerified !== false ||
        typeof row.exception !== 'boolean') {
      throw new Error('Invalid fictional payment record.');
    }

    seen.add(row.reference);

    if (typeof row.amount !== 'string' ||
        !/^-?(?:0|[1-9]\d*)\.\d{2}$/.test(row.amount) ||
        (row.amount.startsWith('-') && row.kind !== 'ADJUSTMENT') ||
        (row.kind === 'ADJUSTMENT' &&
          (typeof row.adjustmentOf !== 'string' ||
           !/^TEST-[A-Z0-9-]{1,30}$/.test(row.adjustmentOf) ||
           row.adjustmentOf === row.reference)) ||
        (row.kind === 'COMPENSATION' && row.adjustmentOf !== null)) {
      throw new Error('Invalid compensation or adjustment.');
    }

    money(row.amount);

    if (row.method !== null &&
        !['ACH', 'CHECK'].includes(row.method)) {
      throw new Error('Unknown payment method.');
    }

    if (row.paymentReference !== null &&
        (typeof row.paymentReference !== 'string' ||
         !/^TEST-[A-Z0-9-]{1,30}$/.test(row.paymentReference))) {
      throw new Error('Untrusted payment reference.');
    }

    if (
      (row.issuedDate === null &&
        (row.method !== null || row.paymentReference !== null ||
         row.settlementCandidateDate !== null)) ||
      (row.issuedDate !== null &&
        (row.method === null || row.paymentReference === null ||
         row.recordedStatus !== 'PAID')) ||
      (row.settlementCandidateDate !== null &&
        row.settlementCandidateDate < row.issuedDate!) ||
      (row.recordedStatus === 'DRAFT' && row.issuedDate !== null)
    ) {
      throw new Error('Conflicting payment issuance evidence.');
    }
  }
}

function status(row: HistoryRow4351): string {
  if (row.recordedStatus === 'PAID') {
    return 'Recorded as Paid - not independently verified';
  }
  if (row.recordedStatus === 'APPROVED') {
    return 'Approved - Not Yet Paid';
  }
  return 'Draft - Not Approved';
}

export function PayrollPaymentHistory4351({
  report,
}: {
  report: PaymentHistory4351;
}): React.JSX.Element {
  validate(report);

  const cell: React.CSSProperties = {
    padding: '10px 12px',
    textAlign: 'left',
    whiteSpace: 'nowrap',
    verticalAlign: 'top',
    borderBottom: '1px solid #D7E3E7',
  };

  return (
    <div
      aria-label="Fictional Payment History records"
      data-test-only="true"
      style={{ color: '#142B3B' }}
    >
      <p>
        Fictional historical records only. Recorded payment status,
        issuance and settlement evidence remain separate.
      </p>
      <div style={{ overflowX: 'auto' }}>
        <table style={{
          width: '100%',
          minWidth: 1650,
          borderCollapse: 'collapse',
        }}>
          <thead>
            <tr>
              {[
                'Recipient', 'Type', 'Amount',
                'Compensation date', 'Payroll period',
                'Payment schedule', 'Recorded status',
                'Issued date', 'Method / reference',
                'Settlement evidence', 'Actual paid date',
                'Exception / adjustment',
              ].map(heading => (
                <th scope="col" key={heading} style={cell}>
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {report.rows.map(row => (
              <tr key={row.reference}>
                <td style={cell}>{row.recipient}</td>
                <td style={cell}>{row.category}</td>
                <td style={cell}>{money(row.amount)}</td>
                <td style={cell}>
                  {row.compensationDate ?? 'Not established'}
                </td>
                <td style={cell}>
                  {row.periodStart} to {row.periodEnd}
                </td>
                <td style={cell}>
                  {row.proposedPaymentDate === null
                    ? 'Not proposed'
                    : `Proposed: ${row.proposedPaymentDate}`}
                </td>
                <td style={cell}>{status(row)}</td>
                <td style={cell}>
                  {row.issuedDate === null
                    ? 'Not issued'
                    : `${row.issuedDate} (recorded)`}
                </td>
                <td style={cell}>
                  {row.method === null
                    ? 'Not recorded'
                    : `${row.method} / ${row.paymentReference}`}
                </td>
                <td style={cell}>
                  {row.settlementCandidateDate === null
                    ? 'Not established'
                    : `${row.settlementCandidateDate} (unverified)`}
                </td>
                <td style={cell}>
                  Not independently established
                </td>
                <td style={cell}>
                  {row.kind === 'ADJUSTMENT'
                    ? `Separate adjustment to ${row.adjustmentOf}`
                    : row.exception ? 'Exception - review required'
                    : 'None recorded'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p style={{ fontSize: 13, color: '#526674' }}>
        No independently verified actual payment dates are available
        in this test contract. Issuance or a settlement candidate
        does not establish receipt or disbursement. No payment
        actions or report exports are enabled.
      </p>
    </div>
  );
}