/**
 * VERIDIAN Step 1907P-4402
 * Fictional Payroll Reports presentation translation only.
 *
 * Does not verify backend scope, approvals, bank evidence, payment,
 * financial totals, real data, or export authorization.
 */
import type {
  PayrollReport4357,
  ReportRow4357,
} from './payroll-reports-4357';

type Record4402 = Record<string, unknown>;

function object4402(value: unknown): Record4402 {
  if (value === null || typeof value !== 'object' ||
      Array.isArray(value)) {
    throw new Error('Fictional report object required.');
  }
  return value as Record4402;
}

function date4402(value: unknown): string {
  if (typeof value !== 'string' ||
      !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    throw new Error('Invalid report date.');
  }
  const parsed = new Date(value + 'T00:00:00.000Z');
  if (!Number.isFinite(parsed.getTime()) ||
      parsed.toISOString().slice(0, 10) !== value) {
    throw new Error('Noncanonical report date.');
  }
  return value;
}

function id4402(value: unknown): string {
  if (typeof value !== 'string' ||
      !/^TEST-[A-Z0-9-]{1,36}$/.test(value)) {
    throw new Error('Synthetic report identifier required.');
  }
  return value;
}

function amount4402(value: unknown, adjustment: boolean): string {
  if (typeof value !== 'string' ||
      !/^-?(?:0|[1-9]\d{0,8})\.\d{2}$/.test(value) ||
      (value.startsWith('-') && !adjustment)) {
    throw new Error('Invalid exact report amount.');
  }
  return value;
}

export function mapFictionalPayrollReports4402(
  payload: unknown
): PayrollReport4357 {
  const data = object4402(payload);

  if (
    data.view !== 'fictional_company_payroll_report_only' ||
    data.backend_scope_verified !== false ||
    data.external_payment_evidence_verified !== false ||
    data.exports_available !== false ||
    data.live_payroll_authorized !== false ||
    !Array.isArray(data.rows) ||
    data.rows.length > 100
  ) {
    throw new Error('Unsafe payroll reporting source.');
  }

  const periodStart = date4402(data.period_start);
  const periodEnd = date4402(data.period_end);
  const start = new Date(periodStart + 'T00:00:00.000Z');
  const end = new Date(periodEnd + 'T00:00:00.000Z');

  if (
    start.getUTCDay() !== 1 ||
    end.getUTCDay() !== 0 ||
    end.getTime() - start.getTime() !== 6 * 86400000
  ) {
    throw new Error('Payroll reporting period must be Monday-Sunday.');
  }

  const references = new Map<string, ReportRow4357>();

  const rows: ReportRow4357[] = data.rows.map(raw => {
    const row = object4402(raw);
    const reference = id4402(row.reference);

    if (references.has(reference)) {
      throw new Error('Duplicate report obligation.');
    }

    if (
      typeof row.recipient !== 'string' ||
      !/^Fictional [A-Za-z ]{1,60}$/.test(row.recipient) ||
      (row.category !== 'employee' &&
       row.category !== 'contractor') ||
      (row.kind !== 'COMPENSATION' &&
       row.kind !== 'ADJUSTMENT') ||
      (row.recorded_status !== 'DRAFT' &&
       row.recorded_status !== 'APPROVED' &&
       row.recorded_status !== 'PAID_RECORDED') ||
      typeof row.first_approval_recorded !== 'boolean' ||
      typeof row.comptroller_approval_recorded !== 'boolean' ||
      typeof row.audit_recorded !== 'boolean' ||
      row.independently_verified_paid_date !== null ||
      row.independently_verified_paid !== false ||
      typeof row.exception !== 'boolean'
    ) {
      throw new Error('Unsafe payroll reporting record.');
    }

    const adjustment = row.kind === 'ADJUSTMENT';
    const adjustmentOf = adjustment
      ? id4402(row.adjustment_of)
      : null;

    if (
      (adjustment &&
       (row.recorded_status !== 'DRAFT' ||
        adjustmentOf === reference)) ||
      (!adjustment && row.adjustment_of !== null)
    ) {
      throw new Error('Invalid adjustment or original compensation.');
    }

    const final = row.recorded_status !== 'DRAFT';

    if (
      (final && (
        !row.first_approval_recorded ||
        !row.comptroller_approval_recorded ||
        !row.audit_recorded
      )) ||
      (!final && (
        row.first_approval_recorded ||
        row.comptroller_approval_recorded ||
        row.audit_recorded
      ))
    ) {
      throw new Error('Contradictory payroll approval evidence.');
    }

    const mapped: ReportRow4357 = {
      reference,
      recipient: row.recipient,
      category: row.category,
      kind: row.kind,
      adjustmentOf,
      amount: amount4402(row.amount, adjustment),
      recordedStatus: row.recorded_status,
      firstApprovalRecorded: row.first_approval_recorded,
      comptrollerApprovalRecorded: row.comptroller_approval_recorded,
      auditRecorded: row.audit_recorded,
      independentlyVerifiedPaidDate: null,
      independentlyVerifiedPaid: false,
      exception: row.exception,
    } as ReportRow4357;

    references.set(reference, mapped);
    return mapped;
  });

  for (const row of rows) {
    if (row.kind !== 'ADJUSTMENT') continue;

    const original = references.get(row.adjustmentOf!);

    if (
      !original ||
      original.kind !== 'COMPENSATION' ||
      original.recipient !== row.recipient ||
      original.category !== row.category
    ) {
      throw new Error('Adjustment lacks matching original compensation.');
    }
  }

  return {
    view: 'fictional_company_payroll_report_only',
    periodStart,
    periodEnd,
    backendScopeVerified: false,
    externalPaymentEvidenceVerified: false,
    exportsAvailable: false,
    livePayrollAuthorized: false,
    rows,
  };
}

export function payrollReportsBoundaryGrantsAccess4402(): false {
  return false;
}
